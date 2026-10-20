# Setup & Instalasi

## 1. Prasyarat

- **Docker** (Engine + Compose plugin, versi terbaru) — untuk menjalankan Postgres, Redis, API, worker, dan frontend sekaligus.
- **Python 3.12** — hanya bila ingin menjalankan backend secara lokal tanpa Docker (development).
- **Node 20** — hanya bila ingin menjalankan frontend secara lokal tanpa Docker (development).
- API key **Google Gemini** (untuk ekstraksi variabel AI) — daftar di [Google AI Studio](https://aistudio.google.com).
- Salah satu provider WhatsApp — lihat [providers.md](providers.md) untuk cara setup:
  - **Resmi (produksi):** Meta Cloud API — butuh access token & Phone Number ID.
  - **Non-resmi (testing):** Baileys sidecar — jalan otomatis via docker compose, pairing via QR.

## 2. Konfigurasi Environment (`.env`)

> ✅ **Terverifikasi:** daftar variabel di bawah sudah dicocokkan dengan `backend/.env.example` dan `backend/app/core/config.py`. Item yang masih ditandai 🔶 belum bisa diverifikasi (file pendukungnya belum ditulis).

Salin file contoh lalu isi nilai aslinya:

```bash
cd wa-blast
cp backend/.env.example backend/.env   # WAJIB di backend/.env (bukan root) — docker-compose.yml membaca env_file: ./backend/.env
```

Isi minimum `.env` (edit sesuai kebutuhan):

```dotenv
# --- Database & cache ---
DATABASE_URL=postgresql+psycopg2://wa:wa@postgres:5432/wablast
REDIS_URL=redis://redis:6379/0

# --- Auth JWT ---
JWT_SECRET=<acak-panjang-min-32-karakter>

# --- User pertama (dibuat otomatis saat startup bila belum ada) ---
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<ganti-sekarang-juga>

# --- AI (opsional di ENV — lebih mudah diatur via UI: Pengaturan → AI) ---
# Tanpa GEMINI_API_KEY (ENV maupun UI), fitur ai-extract fallback graceful.
GEMINI_API_KEY=<kunci-api-gemini-anda>
GEMINI_MODEL=gemini-2.0-flash

# --- Provider WhatsApp (secret via ENV, bukan DB — architecture.md §5.8) ---
# Jalur resmi Meta Cloud API (tanpa ini: mode dry-run):
WA_PHONE_NUMBER_ID=<phone-number-id-meta>
WA_ACCESS_TOKEN=<token-meta>

# Jalur non-resmi Baileys (tanpa BAILEYS_API_URL: mode dry-run):
BAILEYS_API_URL=http://baileys:3001
BAILEYS_API_KEY=<baileys-api-key>

# --- CORS frontend ---
FRONTEND_ORIGINS=http://localhost:5173
```

> **Jangan commit file `.env` ke Git.** Token provider dan `JWT_SECRET` tidak boleh masuk repository.
>
> Catatan: `WA_PHONE_NUMBER_ID`/`WA_ACCESS_TOKEN` adalah nama resmi di backend (bukan `WHATSAPP_*`). Tidak ada variabel webhook verify token terpisah di `.env.example` saat ini.

## 3. Jalankan dengan Docker Compose

```bash
cd wa-blast
docker compose up -d
docker compose ps          # pastikan semua service Running
docker compose logs -f api # lihat log API bila ada masalah
```

Layanan yang dijalankan (terverifikasi terhadap `docker-compose.yml`):

| Service | Isi | Port |
|---|---|---|
| `postgres` | PostgreSQL 16 | internal (tidak di-publish) |
| `redis` | Redis 7 (broker Celery) | internal (tidak di-publish) |
| `api` | FastAPI (uvicorn) | `8000:8000` |
| `worker` | Celery worker (`wa_sender` + `default`, `--concurrency=1`) | internal (tidak di-publish) |
| `beat` | Celery Beat (scheduler) | internal (tidak di-publish) |
| `frontend` | Vue 3 SPA (nginx, serve hasil build) | `5173:80` (buka `http://localhost:5173`) |

## 4. User Pertama

Saat API pertama kali start, aplikasi membaca `ADMIN_USERNAME` dan `ADMIN_PASSWORD` dari environment lalu membuat user awal bila belum ada di tabel `users`. Alurnya:

1. Isi `ADMIN_USERNAME` dan `ADMIN_PASSWORD` di `.env` **sebelum** menjalankan `docker compose up -d` pertama kali.
2. Start stack — user dibuat otomatis saat startup (terverifikasi: `backend/app/main.py` → `on_startup()` memanggil `_seed_admin()`).
3. Login di frontend dengan kredensial tersebut, lalu segera ganti password yang kuat.

> **Login dinonaktifkan secara default (mode single-user lokal):** `docker-compose.yml` menyetel
> `AUTH_DISABLED: "true"` pada service `api`, sehingga aplikasi langsung masuk ke dashboard
> tanpa halaman login (auto-login sebagai user aktif pertama). Cocok untuk pemakaian pribadi
> di mesin sendiri. Untuk **mengaktifkan lagi proteksi login**, ubah menjadi `"false"` lalu
> `docker compose up -d --build`.

## 5. Migrasi Database

Skema database dibuat otomatis via `create_all` SQLAlchemy saat API startup (tidak perlu menjalankan migrasi manual). Ini berlaku untuk instalasi awal/MVP. Terverifikasi: `backend/app/main.py` → `on_startup()` memanggil `Base.metadata.create_all(bind=engine)`.

## 6. URL Akses

Port terverifikasi dari `docker-compose.yml` (final):

| Layanan | URL |
|---|---|
| Frontend (Vue SPA via nginx) | `http://localhost:5173` |
| API (termasuk Swagger UI di `/docs`) | `http://localhost:8000` |
| API backend | `http://localhost:8000` |
| Dokumentasi API (Swagger, bawaan FastAPI) | `http://localhost:8000/docs` |
| Referensi API manual | [api.md](api.md) |

## 7. Berhenti / Reset

```bash
docker compose down          # berhenti, data DB tetap tersimpan di volume
docker compose down -v       # berhenti + HAPUS semua data (DB, Redis) — hati-hati
docker compose build --no-cache api worker  # rebuild setelah ubah kode backend
```

## 8. Troubleshooting Umum

| Gejala | Kemungkinan penyebab & solusi |
|---|---|
| `api` exit/restart loop | Periksa log: `docker compose logs api`. Biasanya `DATABASE_URL` salah atau Postgres belum siap — tunggu beberapa detik lalu restart `api`. |
| Login gagal 401 | Pastikan user pertama dibuat (cek env `ADMIN_USERNAME`/`ADMIN_PASSWORD` sebelum startup pertama). |
| AI extract error / 500 | `GEMINI_API_KEY` kosong atau tidak valid; cek juga kuota API Gemini. |
| Blast tidak jalan (status `queued` terus) | Pastikan service `worker` dan `beat` running; cek log worker untuk error Celery/Redis. |
| Webhook Meta tidak masuk | Meta butuh URL publik HTTPS untuk `/api/webhooks/whatsapp`; `localhost` tidak bisa. Pakai tunnel (mis. ngrok) atau deploy. |
| Kirim via Baileys gagal | Sidecar belum terhubung (belum scan QR di http://localhost:3001/qr) atau service baileys mati. Lihat [providers.md](providers.md). |
| Port sudah dipakai | Ubah mapping port di `docker-compose.yml` (mis. `8001:8000`). |

Bila masalah berlanjut, sertakan output `docker compose logs <service>` saat meminta bantuan.
