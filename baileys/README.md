# Baileys Sidecar (jalur non-resmi / gratis)

Sidecar Node.js yang mengendalikan satu nomor WhatsApp via [Baileys](https://github.com/WhiskeySockets/Baileys)
(protokol WhatsApp Web) dan mengeksposnya sebagai REST API untuk backend Python.

## Cara kerja

1. Service jalan (`docker compose up -d --build`).
2. Buka `http://localhost:3001/qr` di browser, scan QR dari HP **nomor testing**.
3. Sesi tersimpan di volume `baileys_auth` — tidak perlu scan ulang tiap restart.
4. Backend Python (`UnofficialWhatsAppAdapter`) memanggil `POST /send-text`.

## Endpoint

| Method | Path | Auth | Keterangan |
|---|---|---|---|
| GET | `/health` | — | `{ ok: true }` |
| GET | `/status` | — | `{ connected, qr_available, phone, uptime_seconds }` |
| GET | `/qr` | — | Halaman QR pairing (auto-refresh tiap 20 dtk) |
| POST | `/send-text` | `x-api-key` bila diset | Body `{ to, text }` → `{ message_id }`; 409 bila belum terhubung |
| POST | `/logout` | `x-api-key` bila diset | Logout + hapus sesi |

## Environment

| Var | Default | Keterangan |
|---|---|---|
| `PORT` | `3001` | Port listen |
| `AUTH_DIR` | `./auth_info` | Direktori sesi (mount volume di compose) |
| `BAILEYS_API_KEY` | _(kosong)_ | Bila diisi, endpoint POST wajib header `x-api-key` |
| `LOG_LEVEL` | `info` | Level log pino |

## Pengembangan lokal

```bash
npm install
node server.js
# buka http://localhost:3001/qr
```

## ⚠️ Peringatan

Jalur **tidak resmi** — WhatsApp dapat mem-banned permanen nomor yang terdeteksi memakai automasi
ini. **Jangan pakai nomor utama/pribadi/bisnis.** Gunakan nomor testing khusus yang siap direlakan.
