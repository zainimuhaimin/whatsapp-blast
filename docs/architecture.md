# Arsitektur Sistem — Tool Blast WhatsApp

> Status: v1 — 2026-10-16. Dokumen acuan implementasi MVP.
> Stack: FastAPI + SQLAlchemy · Vue 3 + Vite + Tailwind · PostgreSQL · Celery + Redis · Google Gemini · Official WhatsApp Business API (via adapter).

---

## 1. Gambaran Arsitektur

### 1.1 Komponen

| Komponen | Teknologi | Peran |
|---|---|---|
| Frontend SPA | Vue 3 + Vite + Tailwind | Login, Dashboard, Kontak, Template, Campaign Wizard (pilih template → input AI → mapping → review → konfirmasi), monitoring campaign, Test Numbers, Audit Log, Settings |
| Backend API | FastAPI + SQLAlchemy | REST API, JWT auth, audit logging, orkestrasi campaign, render pesan |
| Database | PostgreSQL | Source of truth semua data (kontak, template, campaign, status kirim, audit) |
| Queue | Celery + Redis | Broker + result backend; token bucket rate limit; blacklist token logout |
| Worker pengirim | Celery, queue `wa_sender` (concurrency = 1) | Kirim pesan berurutan dengan jeda acak 5–15 detik antar pesan |
| Worker umum | Celery, queue `default` | Dispatch, retry, campaign terjadwal, webhook |
| Scheduler | Celery Beat | Campaign terjadwal, retry yang jatuh tempo, housekeeping |
| WA Adapter | Interface abstrak `WaProviderAdapter` | Dua implementasi: `OfficialWhatsAppAdapter` (Meta Cloud API) & `UnofficialWhatsAppAdapter` (Baileys sidecar); provider dipilih **per campaign**; seluruh kode bisnis hanya bicara ke interface |
| AI | Google Gemini API (eksternal) | Ekstraksi variabel dari input bebas user → JSON `{nama_variabel: value}` |

### 1.2 Diagram komponen

```
┌──────────────┐      HTTPS       ┌─────────────────────────┐
│  Vue 3 SPA   │ ◄──────────────► │  FastAPI (REST + JWT)   │
│  (Vite+TW)   │                  │  routers / services     │
└──────────────┘                  └────┬────────┬───────────┘
                                       │        │
                              SQLAlchemy│        │ Celery (Redis broker)
                                       ▼        ▼
                               ┌──────────────┐  ┌────────────────────┐
                               │  PostgreSQL  │  │ Celery workers     │
                               │  (source of  │  │ wa_sender (conc.1) │
                               │   truth)     │  │ default queue      │
                               └──────────────┘  └────────┬───────────┘
                                                          │
                                                          ▼  ┌─────────────────┐
                                                          ┌─►│ WaAdapter iface │
                                                          │  │ └ Official WA   │
                                                          │  └────────┬────────┘
                                                          │           │ HTTPS
                                                          │  ┌────────▼────────┐
                                                          │  │ WhatsApp        │
                                                          │  │ Business API    │
                                                          │  └─────────────────┘
                                    ┌─────────────────┐
                                    │ Google Gemini   │◄── ekstraksi variabel
                                    │ API             │
                                    └─────────────────┘
```

### 1.3 Alur data end-to-end

```
1. Login (JWT) ──audit──► 2. Kelola kontak manual (CRUD, blacklist)
3. Buat template ──► versi 1 (variabel {{...}} diekstrak otomatis)
4. Campaign wizard:
   a. Buat campaign → pilih template (versi ter-pin, immutable)
   b. Input bebas ──► Gemini ──► kandidat {variabel: value} ──► user EDIT MANUAL
   c. Tiap variabel dipetakan sumbernya: field KONTAK ({{name}} dsb, bukan dari AI)
      atau NILAI CAMPAIGN (hasil AI, berlaku untuk semua penerima)
   d. Pilih penerima (kontak aktif; blacklist otomatis dikecualikan)
      atau MODE TEST (hanya nomor test terdaftar)
   e. HALAMAN REVIEW: tabel penerima × nilai variabel, sample pesan ter-render,
      total penerima, estimasi durasi, daftar error validasi
   f. KONFIRM & BLAST ──audit──► status queued/scheduled ──► enqueue dispatch
5. Worker wa_sender: per penerima → render pesan final → cek rate limit
   → kirim via adapter → update status → sleep acak 5–15 dtk → penerima berikut
6. Gagal → status failed + next_retry_at (backoff, maks 3x)
7. Webhook provider (opsional) → update delivered / read
8. Dashboard: agregasi status per campaign (terkirim, delivered, dibaca, gagal)
```

Semua aksi penting (login, CRUD, ai-extract, confirm/pause/cancel, ubah settings) menulis baris ke `audit_logs` secara sinkron di API.

### 1.4 Struktur repo (usulan)

```
wa-blast/
├── backend/
│   └── app/
│       ├── main.py
│       ├── core/            # config, security (JWT/bcrypt), db session, audit dep
│       ├── models/          # SQLAlchemy models
│       ├── schemas/         # Pydantic request/response
│       ├── api/routers/     # auth, contacts, templates, campaigns, test_numbers,
│       │                    # settings, audit_logs, webhooks
│       ├── services/        # gemini_service, renderer, campaign_service,
│       │                    # rate_limiter, audit_service
│       ├── wa_adapter/      # base.py (interface), official_whatsapp.py
│       └── worker/          # celery_app.py, tasks/ (sender, campaigns, webhooks)
├── frontend/                # Vue 3 + Vite + Tailwind
│   └── src/                 # views/, components/, stores/, api/
└── docker-compose.yml       # postgres, redis, api, worker, beat, frontend
```

---

## 2. ERD

### 2.1 Tabel dan kolom

**`users`** — disiapkan untuk multi-user; saat ini diisi 1 user.

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | UUID PK, default `gen_random_uuid()` | |
| username | VARCHAR(64) UNIQUE NOT NULL | |
| password_hash | VARCHAR(255) NOT NULL | bcrypt |
| is_active | BOOLEAN DEFAULT true | |
| created_at | TIMESTAMPTZ DEFAULT now() | |
| updated_at | TIMESTAMPTZ DEFAULT now() | |

**`contacts`** — input manual via UI.

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(128) NOT NULL | dipakai untuk `{{name}}` |
| phone | VARCHAR(20) UNIQUE NOT NULL | format E.164, mis. `6281234567890` |
| tag | VARCHAR(64) NULL | segmentasi |
| notes | TEXT NULL | catatan |
| is_blacklisted | BOOLEAN DEFAULT false | opt-out → otomatis dikecualikan dari blast |
| created_at | TIMESTAMPTZ DEFAULT now() | |
| updated_at | TIMESTAMPTZ DEFAULT now() | |

Index: `UNIQUE(phone)`, `idx_contacts_blacklisted (is_blacklisted)`, `idx_contacts_tag (tag)`.

**`templates`** — keluarga template (wadah versi).

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(128) UNIQUE NOT NULL | |
| description | TEXT NULL | |
| created_at / updated_at | TIMESTAMPTZ | |

**`template_versions`** — immutable; setiap edit body = versi baru.

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | UUID PK | |
| template_id | UUID NOT NULL FK → `templates.id` ON DELETE CASCADE | |
| version_number | INT NOT NULL | mulai dari 1, increment per template |
| body | TEXT NOT NULL | isi pesan dengan `{{variabel}}` |
| variables | TEXT[] NOT NULL | hasil ekstraksi regex `\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}` |
| created_at | TIMESTAMPTZ DEFAULT now() | |

Constraint: `UNIQUE(template_id, version_number)`. Index: `idx_template_versions_template (template_id)`.

**`campaigns`**

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(160) NOT NULL | |
| template_version_id | UUID NOT NULL FK → `template_versions.id` | versi ter-pin; tidak berubah walau template diedit |
| status | VARCHAR(24) NOT NULL DEFAULT 'draft' | `draft, review, scheduled, queued, sending, paused, completed, failed, cancelled` |
| provider | VARCHAR(24) NOT NULL DEFAULT 'official' | `official` (Meta Cloud API) atau `unofficial` (Baileys sidecar); menentukan adapter + aturan kirim |
| is_test_mode | BOOLEAN DEFAULT false | true → penerima hanya nomor test |
| send_at | TIMESTAMPTZ NULL | null = kirim segera setelah confirm |
| started_at / finished_at | TIMESTAMPTZ NULL | |
| created_at / updated_at | TIMESTAMPTZ | |

Index: `idx_campaigns_status (status)`, `idx_campaigns_send_at (send_at) WHERE status = 'scheduled'`.

**`campaign_variable_mappings`** — hasil mapping variabel per campaign (setelah AI + edit manual user).

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | UUID PK | |
| campaign_id | UUID NOT NULL FK → `campaigns.id` ON DELETE CASCADE | |
| variable_name | VARCHAR(64) NOT NULL | nama variabel di template, mis. `name`, `promo` |
| source | VARCHAR(16) NOT NULL | `contact` atau `campaign` |
| contact_field | VARCHAR(32) NULL | bila `source='contact'`: `name`, `phone`, atau `tag` |
| value | TEXT NULL | bila `source='campaign'`: nilai hasil AI / edit manual |

Constraint: `UNIQUE(campaign_id, variable_name)`. Index: `idx_cvm_campaign (campaign_id)`.

**`campaign_recipients`** — 1 baris per penerima per campaign; source of truth status pengiriman.

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | UUID PK | |
| campaign_id | UUID NOT NULL FK → `campaigns.id` ON DELETE CASCADE | |
| contact_id | UUID NULL FK → `contacts.id` | NULL untuk nomor test |
| phone | VARCHAR(20) NOT NULL | snapshot nomor saat campaign dibuat |
| status | VARCHAR(16) NOT NULL DEFAULT 'pending' | `pending, sent, delivered, read, failed` |
| retry_count | INT NOT NULL DEFAULT 0 | |
| next_retry_at | TIMESTAMPTZ NULL | jadwal retry berikutnya |
| last_error | TEXT NULL | pesan error terakhir |
| provider_message_id | VARCHAR(128) NULL | id dari provider; untuk matching webhook |
| sent_at / delivered_at / read_at | TIMESTAMPTZ NULL | |
| created_at / updated_at | TIMESTAMPTZ | |

Constraint: `UNIQUE(campaign_id, phone)` (cegah duplikat).
Index: `idx_recipients_campaign_status (campaign_id, status)`, `idx_recipients_provider_msg (provider_message_id)`, `idx_recipients_retry (next_retry_at) WHERE status = 'failed'`.

**`test_numbers`** — nomor untuk sandbox/test mode.

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | UUID PK | |
| label | VARCHAR(64) NOT NULL | mis. "HP saya" |
| phone | VARCHAR(20) UNIQUE NOT NULL | format E.164 |
| is_active | BOOLEAN DEFAULT true | |
| created_at | TIMESTAMPTZ DEFAULT now() | |

**`audit_logs`** — wajib untuk semua aksi penting.

| Kolom | Tipe | Keterangan |
|---|---|---|
| id | BIGSERIAL PK | |
| user_id | UUID NULL FK → `users.id` | |
| action | VARCHAR(64) NOT NULL | mis. `auth.login`, `campaign.confirm_blast` |
| entity_type | VARCHAR(32) NULL | mis. `contact`, `template`, `campaign` |
| entity_id | VARCHAR(64) NULL | id entitas terkait |
| metadata | JSONB NULL | detail tambahan (nilai lama/baru, dsb) |
| ip_address | INET NULL | |
| created_at | TIMESTAMPTZ DEFAULT now() | |

Index: `idx_audit_created (created_at DESC)`, `idx_audit_action (action, created_at DESC)`.

**`settings`** — konfigurasi operasional (bukan secret).

| Kolom | Tipe | Keterangan |
|---|---|---|
| key | VARCHAR(64) PK | |
| value | JSONB NOT NULL | |
| updated_at | TIMESTAMPTZ | |

Key awal: `wa.provider` (`official`/`unofficial`, default per campaign), `wa.rate_limit_per_hour` (default 300), `wa.delay_min_sec` (5), `wa.delay_max_sec` (15), `wa.price_per_message_idr` (JSON per kategori, hanya jalur official), `wa.daily_limit` (batas tier nomor), `gemini.model`. Secret (`GEMINI_API_KEY`, `BAILEYS_API_KEY`, token WA) via environment variable, bukan DB.

### 2.2 Relasi

```
users 1 ─── N audit_logs
templates 1 ─── N template_versions
template_versions 1 ─── N campaigns        (pin versi; versi immutable)
campaigns 1 ─── N campaign_variable_mappings
campaigns 1 ─── N campaign_recipients
contacts 1 ─── N campaign_recipients       (nullable; NULL = nomor test)
```

### 2.3 Diagram ERD (ASCII)

```
┌──────────┐        ┌───────────┐        ┌──────────────┐
│  users   │        │ contacts  │        │  templates   │
├──────────┤        ├───────────┤        ├──────────────┤
│ id PK    │        │ id PK     │        │ id PK        │
│ username │        │ name      │        │ name UQ      │
│ pwd_hash │        │ phone UQ  │        │ description  │
└────┬─────┘        └─────┬─────┘        └──────┬───────┘
     │ 1                  │ 1                   │ 1
     │ N                  │ N                   │ N
┌────▼──────┐      ┌───────▼────────────┐ ┌─────▼──────────────┐
│audit_logs │      │campaign_recipients │ │template_versions   │
├───────────┤      ├────────────────────┤ ├────────────────────┤
│ id PK     │      │ id PK              │ │ id PK              │
│ user_id   │      │ campaign_id FK     │ │ template_id FK     │
│ action    │      │ contact_id FK NULL │ │ version_number     │
│ entity_*  │      │ phone              │ │ body               │
│ metadata  │      │ status             │ │ variables[]        │
│ ip_addr   │      │ retry_count        │ └────────┬───────────┘
└───────────┘      │ next_retry_at      │          │ 1
                   │ provider_msg_id    │          │ N
                   │ sent/deliv/read_at │ ┌────────▼─────────┐
                   └─────────┬──────────┘ │    campaigns     │
                             │ N          ├──────────────────┤
                             │ 1          │ id PK            │
                             └────────────│ name             │
                                          │ template_ver FK  │
                    ┌─────────────────────│ status           │
                    │ 1                   │ is_test_mode     │
                    │ N                   │ send_at          │
          ┌─────────▼──────────────────┐  └──────────────────┘
          │ campaign_variable_       │
          │ mappings                 │
          ├──────────────────────────┤
          │ id PK                    │
          │ campaign_id FK           │
          │ variable_name            │
          │ source (contact/campaign)│
          │ contact_field NULL       │
          │ value NULL               │
          └──────────────────────────┘

┌──────────────┐   ┌──────────┐
│ test_numbers │   │ settings │
├──────────────┤   ├──────────┤
│ id PK        │   │ key PK   │
│ label        │   │ value    │
│ phone UQ     │   └──────────┘
│ is_active    │
└──────────────┘
```

---

## 3. Daftar REST API Endpoints

Base path `/api`. Auth: JWT (httpOnly cookie direkomendasikan; alternatif header `Authorization: Bearer`).

### Auth

| Method | Path | Deskripsi |
|---|---|---|
| POST | `/api/auth/login` | `{username, password}` → token; audit `auth.login` |
| POST | `/api/auth/logout` | Blacklist token di Redis; audit `auth.logout` |
| GET | `/api/auth/me` | Profil user aktif |

### Contacts

| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/contacts?search=&tag=&blacklisted=&page=&limit=` | List + pagination |
| POST | `/api/contacts` | `{name, phone (E.164), tag?, notes?}`; validasi format nomor |
| GET | `/api/contacts/{id}` | Detail |
| PUT | `/api/contacts/{id}` | Update penuh |
| DELETE | `/api/contacts/{id}` | Ditolak bila kontak sudah dipakai campaign (pakai blacklist untuk nonaktif) |
| PATCH | `/api/contacts/{id}/blacklist` | `{is_blacklisted}` — toggle opt-out |

### Templates

| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/templates` | List template + info versi terbaru |
| POST | `/api/templates` | `{name, description?, body}` → buat template + version 1 (variabel diekstrak otomatis) |
| GET | `/api/templates/{id}` | Detail + versi terbaru |
| PUT | `/api/templates/{id}` | Update `name`/`description` saja (bukan body) |
| DELETE | `/api/templates/{id}` | Ditolak bila sudah dipakai campaign |
| GET | `/api/templates/{id}/versions` | List versi |
| POST | `/api/templates/{id}/versions` | `{body}` → `version_number` + 1, ekstrak variabel |
| GET | `/api/templates/{id}/versions/{version}` | Detail satu versi |

### Campaigns — wizard & eksekusi

| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/campaigns?status=` | List campaign |
| POST | `/api/campaigns` | `{name, template_version_id, is_test_mode?, send_at?}` → campaign `draft` |
| GET | `/api/campaigns/{id}` | Detail + mapping + ringkasan count penerima |
| PUT | `/api/campaigns/{id}` | Update draft (`name`, `send_at`, `is_test_mode`) |
| DELETE | `/api/campaigns/{id}` | Hanya bila status `draft` |
| POST | `/api/campaigns/{id}/ai-extract` | `{input_text}` → Gemini mengekstrak kandidat `{variabel: value}` untuk variabel bersumber `campaign`; audit `campaign.ai_extract` |
| GET | `/api/campaigns/{id}/mappings` | Daftar mapping variabel (variable, source, contact_field/value) |
| PUT | `/api/campaigns/{id}/mappings` | Simpan mapping hasil edit manual user (wajib sebelum review) |
| POST | `/api/campaigns/{id}/recipients` | `{contact_ids[]}` → bangun `campaign_recipients` (skip blacklist & duplikat nomor); mode test → pakai `test_numbers` aktif |
| GET | `/api/campaigns/{id}/recipients?status=&page=` | List penerima + status kirim |
| GET | `/api/campaigns/{id}/review` | Payload review: total penerima, tabel variabel × nilai, sample 5 pesan ter-render, estimasi durasi, daftar error validasi |
| POST | `/api/campaigns/{id}/confirm` | Validasi penuh → status `queued` (atau `scheduled` bila `send_at` di masa depan) → enqueue dispatch; audit `campaign.confirm_blast` |
| POST | `/api/campaigns/{id}/pause` | Jeda pengiriman (status `paused`) |
| POST | `/api/campaigns/{id}/resume` | Lanjutkan (kembali `sending`/`queued`) |
| POST | `/api/campaigns/{id}/cancel` | Batalkan; sisa `pending` tidak dikirim |
| GET | `/api/campaigns/{id}/stats` | Agregasi: pending / sent / delivered / read / failed |
| GET | `/api/campaigns/{id}/messages?status=` | Rincian per penerima untuk tabel monitoring |

### Test numbers, settings, audit

| Method | Path | Deskripsi |
|---|---|---|
| GET | `/api/test-numbers` | List nomor test |
| POST | `/api/test-numbers` | `{label, phone}` |
| PUT | `/api/test-numbers/{id}` | Update label/phone/is_active |
| DELETE | `/api/test-numbers/{id}` | Hapus |
| GET | `/api/settings` | Baca konfigurasi operasional |
| PUT | `/api/settings/{key}` | Update satu key (whitelist key saja); audit `settings.update` |
| GET | `/api/audit-logs?action=&from=&to=&page=` | List audit log + filter |

### Webhook provider

| Method | Path | Deskripsi |
|---|---|---|
| POST | `/api/webhooks/whatsapp` | Callback status `delivered`/`read` dari provider → update `campaign_recipients` via `provider_message_id`. ⚠️ Butuh konfirmasi format payload & ketersediaan webhook dari riset provider. |

---

## 4. Daftar Celery Tasks

### Queue `wa_sender` (concurrency = 1, pengiriman berurutan)

| Task | Deskripsi |
|---|---|
| `sender.dispatch_campaign(campaign_id)` | Tugas utama, **idempotent**: loop penerima berstatus `pending` → render pesan final → cek token bucket rate limit (Redis) → kirim via `WaProviderAdapter` → update status/`provider_message_id` → `sleep(random 5–15 dtk)`. Berhenti bila campaign di-`pause`/`cancel`. Selesai → `completed` (atau `failed` bila error fatal). Aman di-restart: hanya memproses `pending`. |

### Queue `default`

| Task | Deskripsi |
|---|---|
| `campaigns.enqueue_due()` | Dipicu Beat tiap 1 menit: campaign `scheduled` dengan `send_at <= now()` → `queued` + panggil `dispatch_campaign`. |
| `campaigns.retry_due()` | Dipicu Beat tiap 5 menit: recipient `failed` dengan `retry_count < 3` dan `next_retry_at <= now()` → kembalikan ke `pending` (diproses dispatch yang berjalan / trigger dispatch baru). |
| `webhooks.handle_status_update(payload)` | Proses callback provider → update `delivered`/`read` berdasarkan `provider_message_id`. |
| `maintenance.cleanup_tokens()` | Dipicu Beat harian: hapus blacklist token kedaluwarsa di Redis. |

### Kebijakan retry

Gagal kirim ke-1 → `next_retry_at` +5 menit; ke-2 → +30 menit; ke-3 → +2 jam; setelah 3x → `failed` final dengan `last_error` terisi.

### Estimasi durasi (ditampilkan di halaman review)

```
eta_detik = jumlah_penerima × rata-rata delay (10 dtk, dari rentang 5–15)
batas_rate = jumlah_penerima / wa.rate_limit_per_hour  (jam)
estimasi ditampilkan = maks(eta_detik, batas_rate) → diformat "± X menit"
```

---

## 5. Keputusan Desain Penting

1. **Sumber variabel eksplisit** — setiap variabel template dipetakan ke `contact` (diambil dari field kontak: `name`/`phone`/`tag`, **bukan dari AI**) atau `campaign` (nilai dari Gemini yang berlaku untuk semua penerima dan **wajib bisa diedit manual** sebelum lanjut). Ini mencegah AI mengarang data personal penerima.
2. **Template versioning immutable** — campaign me-pin `template_version_id`; edit body selalu melahirkan versi baru. Campaign lama tidak pernah berubah walau template diedit kemudian.
3. **DB sebagai source of truth status kirim** — tiap penerima = 1 baris di `campaign_recipients`; dispatch idempotent (hanya memproses `pending`) sehingga aman bila worker restart di tengah jalan.
4. **Satu worker pengirim berurutan** (concurrency 1) + jeda acak 5–15 detik + token bucket per-jam di Redis = throttling anti-ban. Throughput kasar ≈ 240–720 pesan/jam tergantung delay dan limit.
5. **Snapshot nomor** — `campaign_recipients.phone` disalin saat penerima dibangun; edit kontak setelahnya tidak mengubah campaign yang sudah berjalan.
6. **Validasi E.164** saat input kontak/nomor test (regex + disarankan library `phonenumbers`).
7. **Audit log sinkron** di lapisan API untuk semua aksi penting: `auth.login/logout`, `contact.*`, `template.*`, `campaign.create/update/delete/ai_extract/recipients.build/confirm/pause/resume/cancel`, `test_number.*`, `settings.update`.
8. **Secret via ENV** (`GEMINI_API_KEY`, token/secret WA provider), tidak disimpan di DB.
9. **Statistik on-read** via agregasi SQL per request; dimaterialisasi/di-cache belakangan bila terbukti lambat.
10. **Auth** — JWT access pendek (±60 menit) + refresh (±7 hari), httpOnly cookie; logout mem-blacklist token di Redis sampai kedaluwarsa.
11. **Prompt Gemini** — system prompt berbahasa Indonesia: "ekstrak hanya nilai untuk daftar variabel berikut dari teks user, kembalikan JSON murni `{nama_variabel: value}`, kosongkan string bila tidak ditemukan, jangan mengarang". Model name configurable via settings.
12. **Mode test** — campaign `is_test_mode=true` hanya mengirim ke `test_numbers` aktif; UI menampilkan banner jelas agar tidak tertukar dengan blast asli.

## 6. Konfirmasi dari Riset Provider (2026-10-16 — semua asumsi di bawah SUDAH TERKONFIRMASI)

Hasil riset official WhatsApp Business Platform (Meta Cloud API, sumber: developers.facebook.com + help-center.qontak.com Okt 2026):

- [x] **Template approval WAJIB** — semua pesan proaktif/di luar 24-jam window HARUS pakai template yang di-approve Meta. Approval umumnya menit–jam (marketing 48–72 jam). Kategori: Marketing / Utility / Authentication. **Implikasi desain:** `template_versions` butuh kolom tambahan `provider_template_name` (nama template terdaftar di Meta) + `approval_status` (`draft`/`submitted`/`approved`/`rejected`) + `provider_category`. Campaign hanya bisa confirm bila versi ter-pin berstatus `approved`.
- [x] **Format parameter: named DIDUKUNG** — template bisa didaftarkan dengan `parameter_format` NAMED sehingga `{{nama}}` kita dipetakan 1:1 ke parameter bernama provider (nama harus persis sama). Alternatif POSITIONAL `{{1}}` juga ada. Maks ~10 parameter, body maks 1024 karakter, Bahasa Indonesia didukung (kode `id`).
- [x] **Aturan 24-jam window** — teks bebas HANYA boleh sebagai balasan dalam customer-service window. Blast = selalu via template. Opt-in eksplisit penerima WAJIB (tercatat, mudah opt-out).
- [x] **Webhook status tersedia** — Cloud API mendukung webhook delivery report (`delivered`/`read`) dengan verifikasi signature; butuh URL publik HTTPS untuk endpoint `/api/webhooks/whatsapp`.
- [x] **Rate limit resmi** — Cloud API ~80 pesan/detik (sumber pihak ketiga). Throttle kita (delay acak 5–15 dtk, ±240–720 pesan/jam, concurrency 1) jauh di bawah itu dan aman. Default `wa.rate_limit_per_hour = 300` tetap dipakai sebagai pengaman anti-ban, bukan karena limit provider.
- [x] **Pricing: PER-PESAN** (sejak 1 Jul 2025, bukan per-conversation lagi). Tarif Indonesia per pesan ter-deliver (Okt 2026): Marketing **Rp 627,33** · Utility **Rp 366,65** · Authentication **Rp 366,65** · Service **Rp 356,65**. Free tier: 1.000 pesan service/bulan/nomor. **Implikasi desain:** halaman review WAJIB menampilkan estimasi biaya = jumlah_penerima × tarif kategori template. Tambah `settings.wa.price_per_message_idr` (JSON per kategori) + kolom `provider_category` di `template_versions`.
- [x] **Messaging limits (nomor baru): 250** pesan/24 jam → 2.000 (setelah verifikasi bisnis) → 10.000 → 100.000 → unlimited (otomatis bila kualitas hijau + utilisasi ≥50%). **Implikasi:** untuk blast 500 kontak, verifikasi bisnis dulu ATAU bagi ke 2 hari; rencanakan warm-up nomor. Tambah validasi di `confirm`: tolak bila jumlah penerima > limit tier saat ini (konfigurabel via `settings.wa.daily_limit`).
- [ ] **Model Gemini** — nama model stabil + pricing ditentukan saat implementasi (bukan bagian riset WA).

## 7. Jalur Ganda: Resmi vs Non-Resmi (Unofficial)

User meminta dua jalur pengiriman dalam satu tool: **resmi** (produksi) dan **gratis/non-resmi** (testing). Keduanya di belakang interface `WaProviderAdapter` yang sama; campaign memilih jalur via kolom `campaigns.provider`.

| Aspek | Resmi — Meta Cloud API | Non-resmi — Baileys (self-hosted) |
|---|---|---|
| Biaya | Rp 627,33/pesan marketing (ID) | **Rp 0** — free tier 1.000 pesan/bulan (termasuk API + webhook + autoreply)【8420453111398146070†L37-L40】 |
| Setup | Meta Business Manager + verifikasi bisnis + nomor khusus + payment | Jalankan sidecar + **scan QR** di http://localhost:3001/qr |
| Template | WAJIB template approve Meta (marketing 48–72 jam) | **Teks bebas**, tanpa approval |
| Limit | 250 → 2.000 → … → unlimited per 24 jam | Mengikuti kuota paket (free: 1.000/bln) |
| Risiko | Rendah bila opt-in & template benar | **Nomor bisa ke-banned WA** (jalur tidak resmi) |
| Status kirim | Webhook `delivered`/`read` resmi | Webhook tersedia (detail format saat implementasi) |

**Aturan desain untuk jalur non-resmi:**
1. **Jangan pakai nomor WA utama/pribadi** — gunakan nomor testing khusus. UI menampilkan peringatan eksplisit saat memilih provider `unofficial`.
2. Validasi template-version `approved` hanya berlaku untuk jalur `official`; jalur `unofficial` boleh kirim teks bebas dari template mana pun.
3. Estimasi biaya di halaman review: **Rp 0** untuk unofficial .
4. Rekomendasi pemakaian: unofficial untuk testing template/variabel/AI-mapping; official untuk blast produksi.
5. `BAILEYS_API_KEY` (opsional) disimpan via ENV, bukan di DB.

**Keputusan provider (rekomendasi riset): Meta Cloud API langsung, tanpa BSP** — biaya platform Rp 0, hanya tarif Meta per pesan; REST API resmi + webhook; throughput tertinggi; tanpa lock-in vendor. Syarat: akun Meta + Business Manager + verifikasi bisnis + display name approve + nomor khusus + metode pembayaran. Alternatif: Twilio (pay-as-you-go, tanpa biaya bulanan) bila butuh SDK matang; WATI bila butuh UI no-code.
