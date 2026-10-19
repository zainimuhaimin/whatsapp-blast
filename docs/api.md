# Referensi REST API

Ringkasan semua endpoint. Base path: `/api`. Autentikasi: **JWT** (httpOnly cookie direkomendasikan; alternatif header `Authorization: Bearer <token>`).

Sumber desain: `architecture.md` §3. Detail skema request/response final mengikuti implementasi backend (Pydantic schemas) — bila berbeda dengan tabel ini, yang berlaku adalah kode.

## Auth

| Method | Path | Deskripsi | Body / Catatan |
|---|---|---|---|
| POST | `/api/auth/login` | Login | `{username, password}` → token; audit `auth.login` |
| POST | `/api/auth/logout` | Logout | Token di-blacklist di Redis; audit `auth.logout` |
| GET | `/api/auth/me` | Profil user yang sedang login | — |

## Kontak

| Method | Path | Deskripsi | Body / Catatan |
|---|---|---|---|
| GET | `/api/contacts` | List + pagination | Query: `search`, `tag`, `blacklisted`, `page`, `limit` |
| POST | `/api/contacts` | Tambah kontak | `{name, phone (E.164), tag?, notes?}` — validasi format nomor |
| GET | `/api/contacts/{id}` | Detail kontak | — |
| PUT | `/api/contacts/{id}` | Update penuh kontak | Field kontak |
| DELETE | `/api/contacts/{id}` | Hapus kontak | **Ditolak** bila kontak sudah dipakai campaign — pakai blacklist untuk menonaktifkan |
| PATCH | `/api/contacts/{id}/blacklist` | Toggle opt-out | `{is_blacklisted}` |

## Template

| Method | Path | Deskripsi | Body / Catatan |
|---|---|---|---|
| GET | `/api/templates` | List template + info versi terbaru | — |
| POST | `/api/templates` | Buat template + version 1 | `{name, description?, body}` — variabel diekstrak otomatis dari `{{...}}` |
| GET | `/api/templates/{id}` | Detail + versi terbaru | — |
| PUT | `/api/templates/{id}` | Update `name`/`description` | Hanya metadata — **bukan** body |
| DELETE | `/api/templates/{id}` | Hapus template | **Ditolak** bila sudah dipakai campaign |
| GET | `/api/templates/{id}/versions` | List semua versi | — |
| POST | `/api/templates/{id}/versions` | Buat versi baru | `{body}` → `version_number` + 1, ekstrak variabel |
| GET | `/api/templates/{id}/versions/{version}` | Detail satu versi | — |

## Campaign — Wizard & Eksekusi

| Method | Path | Deskripsi | Body / Catatan |
|---|---|---|---|
| GET | `/api/campaigns` | List campaign | Query: `status` |
| POST | `/api/campaigns` | Buat campaign (status `draft`) | `{name, template_version_id, is_test_mode?, send_at?}` |
| GET | `/api/campaigns/{id}` | Detail + mapping + ringkasan jumlah penerima | — |
| PUT | `/api/campaigns/{id}` | Update draft | `{name?, send_at?, is_test_mode?}` |
| DELETE | `/api/campaigns/{id}` | Hapus campaign | Hanya bila status `draft` |
| POST | `/api/campaigns/{id}/ai-extract` | Ekstraksi variabel via Gemini | `{input_text}` → kandidat `{variabel: value}` untuk variabel bersumber `campaign`; audit `campaign.ai_extract` |
| GET | `/api/campaigns/{id}/mappings` | Daftar mapping variabel | Kolom: variable, source, contact_field/value |
| PUT | `/api/campaigns/{id}/mappings` | Simpan mapping hasil edit manual | **Wajib** sebelum review |
| POST | `/api/campaigns/{id}/recipients` | Bangun daftar penerima | `{contact_ids[]}` — blacklist & duplikat nomor otomatis dilewati; mode test → pakai `test_numbers` aktif |
| GET | `/api/campaigns/{id}/recipients` | List penerima + status kirim | Query: `status`, `page` |
| POST | `/api/campaigns/{id}/recipients/{rid}/retry` | Retry manual 1 penerima gagal | Reset ke `pending`; campaign `completed` → `queued` + trigger dispatch |
| GET | `/api/campaigns/{id}/chat-links` | Link wa.me per penerima (kirim manual) | Query: `page`, `limit` → `{phone, name, message, wa_url}` |
| GET | `/api/campaigns/{id}/review` | Payload halaman review | Total penerima, tabel variabel × nilai, sample 5 pesan ter-render, estimasi durasi & biaya, daftar error validasi |
| POST | `/api/campaigns/{id}/confirm` | Konfirmasi & mulai blast | Validasi penuh → `queued` (atau `scheduled` bila `send_at` di masa depan) → enqueue dispatch; audit `campaign.confirm_blast` |
| POST | `/api/campaigns/{id}/pause` | Jeda pengiriman | Status → `paused` |
| POST | `/api/campaigns/{id}/resume` | Lanjutkan pengiriman | Kembali ke `sending`/`queued` |
| POST | `/api/campaigns/{id}/cancel` | Batalkan campaign | Sisa `pending` tidak dikirim |
| GET | `/api/campaigns/{id}/stats` | Agregasi status | `pending / sent / delivered / read / failed` |
| GET | `/api/campaigns/{id}/messages` | Rincian per penerima (tabel monitoring) | Query: `status` |

**Status campaign:** `draft → review → scheduled / queued → sending → completed`, dengan cabang `paused`, `failed`, `cancelled`.

**Status penerima:** `pending → sent → delivered → read`, atau `failed` (retry otomatis maks 3x: +5 mnt → +30 mnt → +2 jam).

## Test Numbers

| Method | Path | Deskripsi | Body / Catatan |
|---|---|---|---|
| GET | `/api/test-numbers` | List nomor test | — |
| POST | `/api/test-numbers` | Tambah nomor test | `{label, phone}` |
| PUT | `/api/test-numbers/{id}` | Update nomor test | `{label?, phone?, is_active?}` |
| DELETE | `/api/test-numbers/{id}` | Hapus nomor test | — |

## File Uploads — Blast dari File

| Method | Path | Deskripsi | Body / Catatan |
|---|---|---|---|
| POST | `/api/file-uploads/parse` | Upload & parse CSV/XLSX | Multipart `file`; header → variabel ternormalisasi; maks 10 MB / 5000 baris |
| POST | `/api/file-uploads/{id}/preview` | Preview render 5 baris | `{message, phone_variable}` → pesan ter-render + `unknown_variables` + `skipped_rows` |
| POST | `/api/file-uploads/{id}/create-campaign` | Buat campaign dari file | `{name, message, phone_variable, provider, is_test_mode}` → template + campaign draft + recipients + override per baris |

## Settings & Audit

| Method | Path | Deskripsi | Body / Catatan |
|---|---|---|---|
| GET | `/api/settings` | Baca konfigurasi operasional | Key: `wa.provider`, `wa.rate_limit_per_hour`, `wa.delay_min_sec`, `wa.delay_max_sec`, `wa.price_per_message_idr`, `wa.daily_limit`, `gemini.model`, … |
| PUT | `/api/settings/{key}` | Update satu key | Hanya key yang di-whitelist; audit `settings.update` |
| GET | `/api/audit-logs` | List audit log + filter | Query: `action`, `from`, `to`, `page` |

## Webhook Provider

| Method | Path | Deskripsi | Body / Catatan |
|---|---|---|---|
| POST | `/api/webhooks/whatsapp` | Callback status dari provider | `delivered`/`read` → update `campaign_recipients` via `provider_message_id`. ⚠️ Format payload & ketersediaan webhook per provider **perlu verifikasi saat implementasi** (lihat `architecture.md` §3 & §6). |

## Kode Status Umum

| Kode | Arti |
|---|---|
| `200` | OK |
| `201` | Created (POST berhasil membuat resource) |
| `400` | Validasi gagal (lihat daftar error di response) |
| `401` | Belum login / token tidak valid |
| `404` | Resource tidak ditemukan |
| `409` | Konflik — mis. hapus kontak/template yang sudah dipakai campaign |
| `422` | Body request tidak sesuai skema |
