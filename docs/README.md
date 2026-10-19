# Tool Blast WhatsApp

Tool internal untuk pengiriman pesan massal (blast) WhatsApp — single-user, dengan input variabel dinamis via AI, halaman review & konfirmasi sebelum kirim, throttling anti-ban, tracking status per pesan, retry otomatis, dan dukungan **dual provider**: jalur resmi (Meta WhatsApp Cloud API) untuk produksi dan jalur non-resmi (Baileys self-hosted) untuk testing.

## Fitur Utama

- **Kontak**: CRUD manual (nama, nomor E.164, tag, catatan), blacklist/opt-out otomatis dikecualikan dari blast.
- **Template**: body dengan variabel `{{nama}}`, versioning immutable (edit body = versi baru; campaign me-pin versi terpakai).
- **Campaign Wizard**: pilih template → input bebas dibantu **AI (Google Gemini)** mengekstrak nilai variabel → mapping variabel (sumber *contact* atau *campaign*) → pilih penerima → **halaman review** (tabel penerima × nilai, sample pesan ter-render, estimasi durasi & biaya) → konfirmasi blast.
- **Dua jalur pengiriman** (pilih per campaign): resmi via Meta Cloud API, atau gratis via Baileys self-hosted (non-resmi, khusus testing).
- **Throttling anti-ban**: 1 worker pengirim berurutan, jeda acak 5–15 detik, token bucket per-jam.
- **Tracking**: status per penerima (`pending → sent → delivered → read → failed`), retry otomatis maks 3x dengan backoff, webhook status provider.
- **Mode test / sandbox**: kirim hanya ke nomor test terdaftar, dengan banner jelas di UI.
- **Audit log**: semua aksi penting (login, CRUD, AI extract, confirm/pause/cancel, settings) tercatat sinkron.
- **Scheduling**: blast bisa dijadwalkan (`send_at`) via Celery Beat.

## Tech Stack

| Lapisan | Teknologi |
|---|---|
| Frontend | Vue 3 + Vite + Tailwind |
| Backend | FastAPI + SQLAlchemy (Pydantic) |
| Database | PostgreSQL |
| Queue | Celery + Redis (queue `wa_sender` concurrency 1 + queue `default`) |
| Scheduler | Celery Beat |
| AI | Google Gemini API |
| Provider WA | Adapter abstrak `WaProviderAdapter` → `OfficialWhatsAppAdapter` (Meta Cloud API) / `UnofficialWhatsAppAdapter` (Baileys sidecar) |

## Struktur Repo

```
wa-blast/
├── docs/                    # Dokumentasi (direktori ini)
│   ├── README.md            # Overview ini
│   ├── setup.md             # Instalasi & konfigurasi
│   ├── user-guide.md        # Panduan pakai (non-teknis)
│   ├── providers.md         # Setup Meta Cloud API & Baileys
│   ├── api.md               # Referensi REST API
│   └── architecture.md      # Desain arsitektur lengkap (ERD, Celery, dll)
├── backend/                 # FastAPI (lihat struktur di architecture.md §1.4)
├── frontend/                # Vue 3 + Vite + Tailwind
└── docker-compose.yml       # postgres, redis, api, worker, beat, frontend
```

## Quickstart

```bash
cd wa-blast
cp backend/.env.example backend/.env   # lalu isi kredensial (WAJIB di backend/.env)
docker compose up -d
```

Frontend: lihat [setup.md](setup.md) untuk URL akses dan troubleshooting.

## Dokumentasi

- [Setup & Instalasi](setup.md) — prasyarat, `.env`, user pertama, migrasi, troubleshooting
- [Panduan Pengguna](user-guide.md) — alur end-to-end kontak → template → campaign → monitoring
- [Provider: Resmi vs Non-Resmi](providers.md) — setup Meta Cloud API & Baileys, perbandingan biaya & risiko
- [Referensi API](api.md) — tabel semua endpoint REST
- [Arsitektur Sistem](architecture.md) — ERD, Celery tasks, keputusan desain, hasil riset provider
