# ASUMSI.md — Keputusan implementasi backend WA Blast MVP

Tanggal: 2026-10-16. Source of truth: `../design/architecture-draft.md`.

## 1. Migrasi: create_all(), tanpa Alembic
Sesuai instruksi tugas (keputusan: simpel untuk MVP). `Base.metadata.create_all()`
dijalankan di event startup `app/main.py`. Konsekuensi: perubahan skema di
kemudian hari butuh ALTER TABLE manual atau reset database.

## 2. UUID PK: default ganda
Dokumen memakai `gen_random_uuid()` (Postgres). Agar `create_all` tetap jalan
di SQLite saat testing lokal, kolom id memakai `default=uuid.uuid4` (python-side)
**plus** `server_default=text("gen_random_uuid()")` untuk Postgres. `audit_logs.id`
BIGSERIAL via `BigInteger(autoincrement=True)`.

## 3. Tipe Postgres-spesifik
`JSONB` (settings.value, audit_logs.metadata), `ARRAY(Text)` (template_versions.variables),
`INET` (audit_logs.ip_address) dipakai sesuai ERD karena target DB adalah Postgres 16.

## 4. Gemini: fallback graceful, bukan error
Bila `GEMINI_API_KEY` kosong atau package gagal/error saat generate, `ai-extract`
mengembalikan `{"values": {}, "ai_available": false}` dan tetap menyimpan
mapping kosong — campaign bisa dilanjutkan dengan input manual via PUT mappings.

## 5. Adapter dry-run
Kedua adapter (`OfficialWhatsAppAdapter`, `UnofficialWhatsAppAdapter`) memeriksa
`is_configured()`; bila kredensial kosong mereka me-log warning dan mengembalikan
`provider_message_id="dry-run-<hex>"` **tanpa request HTTP**. Aturan tegas dari
tugas: tidak pernah kirim pesan sungguhan tanpa kredensial terkonfigurasi.

## 6. Rate limit: token bucket Redis (Lua, atomic)
Diimplementasikan sebagai token bucket murni (kapasitas = limit/jam, refill linear
per detik) via script Lua agar atomic. Bila bucket habis di tengah dispatch,
task menjadwalkan ulang dirinya 60 detik kemudian (countdown=60).

## 7. Retry
Gagal kirim ke-1 → `next_retry_at` +5 menit; ke-2 → +30 menit; ke-3 → +2 jam;
setelah 3x (`retry_count >= 3`) → `failed` final (`next_retry_at=NULL`).
`campaigns.retry_due` (Beat tiap 5 menit) mengembalikan `failed` yang masih
memiliki jatah retry ke `pending` dan me-trigger dispatch untuk campaign aktif.

## 8. Endpoint tambahan di luar section 3 dokumen
- `POST /api/auth/refresh` — menukar refresh token (7 hari) menjadi access token
  baru; dibutuhkan agar pasangan access 60 mnt + refresh 7 hari benar-benar berguna.
- `PATCH /api/templates/{id}/versions/{version}` — update metadata approval Meta
  (`approval_status`, `provider_category`, `provider_template_name`) tanpa
  mengubah body (body tetap immutable). Tanpa ini, status `approved` tidak bisa
  dicapai dan jalur official tidak pernah bisa confirm.
- `GET /api/webhooks/whatsapp` — verifikasi `hub.challenge` Meta saat
  mendaftarkan webhook (wajib oleh Meta, tidak ada di daftar endpoint).

## 9. Validasi confirm (400/422)
`POST /api/campaigns/{id}/confirm` mengembalikan HTTP 422 dengan
`{"validation_errors": [...]}` bila ada aturan yang dilanggar (template belum
approved untuk official, 0 penerima, variabel belum ter-mapping, penerima
melebihi `wa.daily_limit`).

## 10. Review: estimasi biaya & durasi
- Durasi: `maks(n × 10 detik, n / wa.rate_limit_per_hour jam)` → format "± X menit".
- Biaya official: `n × tarif kategori` dari `settings.wa.price_per_message_idr`
  (default: marketing 627.33, utility 366.65, authentication 366.65, service 356.65 —
  tarif IDR Indonesia per riset Okt 2026). Unofficial: Rp 0.
- `sample_messages`: 5 pesan pertama ter-render (atau kurang bila penerima < 5).

## 11. Normalisasi nomor telepon
Input dinormalisasi ke digit E.164 tanpa `+` (mis. `6281234567890`): spasi/strip/
kurung dibuang, awalan `0` lokal diasumsikan Indonesia (`62`), lalu divalidasi
regex + library `phonenumbers` bila tersedia.

## 12. Seed
- User admin pertama dibuat saat startup dari `ADMIN_USERNAME`/`ADMIN_PASSWORD`
  **hanya bila tabel users kosong**.
- Default settings (`wa.*`, `gemini.model`) di-seed ke tabel `settings` bila key
  belum ada; nilai DB selalu menang atas default.

## 13. Webhook
Router hanya mengantrekan payload ke task Celery `webhooks.handle_status_update`
(queue default). Parser mendukung format Meta Cloud API
(`entry[].changes[].value.statuses[]`) + fallback generik (`{message_id/id, status}`).
Verifikasi signature Meta belum diimplementasikan (format kunci rahasia app
ditentukan saat setup webhook produksi).

## 14. Test mode
`POST /api/campaigns/{id}/recipients` pada campaign `is_test_mode=true`
mengabaikan `contact_ids` dan memakai semua `test_numbers` yang aktif
(`contact_id=NULL`).

## 15. CORS
`FRONTEND_ORIGINS` (default `*` untuk dev); cookie auth memakai `httponly`,
`samesite=lax`.

## 16. Pin bcrypt==4.0.1
`passlib[bcrypt]` tetap tercantum di requirements, ditambah pin `bcrypt==4.0.1`
karena passlib 1.7.4 gagal total dengan bcrypt>=4.1 (wrap-bug check melempar
`ValueError: password cannot be longer than 72 bytes`).

## 17. AuditLog: atribut `meta` -> kolom `metadata`
SQLAlchemy Declarative mencadangkan nama `metadata`, sehingga kolom DB
`metadata` (sesuai ERD) dipetakan ke atribut Python `meta`
(`mapped_column("metadata", JSONB)`). API tetap mengekspos field `metadata`.

## 18. Keterbatasan verifikasi lokal
Tidak ada Postgres/Redis di lingkungan build, sehingga verifikasi memakai
SQLite (dengan shim kompilasi tipe) + fakeredis + TestClient: 40 check API
dan 11 check worker lolos. Script Lua token bucket lolos cek sintaks
(`lupa`) tetapi belum diuji terhadap Redis asli — dijalankan pertama kali
di `docker compose up`.
