# Provider: Resmi vs Non-Resmi

Tool ini mendukung **dua jalur pengiriman** dalam satu antarmuka. Anda memilih jalurnya **per campaign**.

> ℹ️ Angka harga, limit, dan prosedur di bawah dirangkum dari riset WhatsApp Business Platform (Oktober 2026, sumber: dokumen resmi Meta via indeks + help center BSP). Kebijakan Meta bisa berubah — untuk angka final, cek [dokumen harga resmi Meta](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing) dan [batas messaging resmi](https://developers.facebook.com/documentation/business-messaging/whatsapp/messaging-limits).

---

## A. Setup Meta Cloud API (Jalur Resmi — untuk produksi)

Rekomendasi riset: pakai **Meta Cloud API langsung, tanpa BSP** (perantara). Biaya platform Rp 0 — Anda hanya membayar tarif pesan Meta. Syaratnya Anda (atau tim teknis) bisa mengintegrasikan REST API + webhook, yang sudah ditangani tool ini.

### Langkah-langkah

1. **Buat Meta App** — buka [developers.facebook.com](https://developers.facebook.com), daftar sebagai developer, buat aplikasi baru dengan use case **WhatsApp**. Di halaman "API Setup" Anda bisa menambah nomor telepon dan mengirim pesan pertama.
2. **Siapkan Business Portfolio (Business Manager)** — buat atau pilih portfolio bisnis; nomor WhatsApp Business Anda terdaftar di bawahnya.
3. **Verifikasi bisnis** — siapkan dokumen legal perusahaan dan **website asli yang jelas** (hanya link-in-bio sering ditolak). Verifikasi juga menaikkan limit pesan (lihat bawah).
4. **Ajukan display name** — nama tampilan bisnis (yang terlihat penerima) harus di-review dan di-approve Meta.
5. **Siapkan nomor telepon khusus** — nomor ini **tidak boleh aktif** di WhatsApp biasa/bisnis. Bila nomornya sedang dipakai, hapus dulu akun WhatsApp-nya (butuh waktu beberapa menit hingga nomor tersedia untuk didaftarkan).
6. **Tambahkan metode pembayaran** — wajib; tanpa ini template message tidak bisa dikirim.
7. **Buat & daftarkan template** — semua pesan proaktif (blast) **WAJIB** memakai template yang di-approve Meta. Di dashboard Meta:
   - Pilih kategori: **Marketing** (promo/pengumuman), **Utility** (transaksional: order/booking/reminder), atau **Authentication** (OTP). Pilih yang benar — Meta bisa mengubah kategori sepihak dan salah kategori menaikkan biaya + menurunkan rating.
   - Tulis body (maks **1024 karakter**), bahasa **Indonesia** (kode `id`).
   - Variabel bisa **named** `{{nama}}` (dipetakan 1:1 ke variabel template tool ini — nama harus persis sama) atau **positional** `{{1}}`. Maks ~10 parameter.
   - Setiap parameter wajib diberi **contoh nilai** (example).
   - Approval: umumnya **menit–jam**; kategori **marketing 48–72 jam**. Bila ditolak, ada alasan dan bisa edit + resubmit.
   - Tips lolos: tujuan pesan jelas, kategori tepat, tidak ada konten terlarang; untuk marketing sebaiknya ada instruksi opt-out.
8. **Pasang webhook (di tool ini)** — sediakan URL publik HTTPS ke endpoint `/api/webhooks/whatsapp` agar status `delivered`/`read` masuk otomatis ke dashboard monitoring. Verifikasi signature didukung Cloud API.

### Tarif Indonesia (per pesan ter-deliver, Okt 2026)

| Kategori | Tarif/pesan |
|---|---|
| Marketing | **Rp 627,33** |
| Utility | Rp 366,65 |
| Authentication | Rp 366,65 |
| Service (balasan dalam 24-jam window) | Rp 356,65 |

- Model harga Meta sejak 1 Jul 2025: **per pesan yang ter-deliver** (bukan per conversation).
- Free tier: **1.000 pesan service/bulan/nomor** gratis. Pesan dari iklan Click-to-WhatsApp (free entry point) gratis.
- Contoh: blast **500 kontak** template marketing ≈ 500 × Rp 627,33 ≈ **Rp 314 ribu**.

### Messaging limits (tier nomor baru)

| Tier | Batas pesan unik / 24 jam | Cara naik |
|---|---|---|
| Baru | **250** | — |
| 2 | 2.000 | Selesaikan verifikasi bisnis |
| 3 | 10.000 | Otomatis bila kualitas hijau + utilisasi ≥50% limit dalam 7 hari |
| 4 | 100.000 | Otomatis (syarat sama) |
| 5 | Unlimited | Otomatis (syarat sama) |

> Implikasi praktis: nomor baru hanya bisa blast **250 kontak unik/hari**. Untuk 500 kontak: verifikasi bisnis dulu (naik ke 2.000) atau bagi ke 2 hari. Tool ini memvalidasi di halaman review — konfirmasi ditolak bila penerima melebihi limit tier (dikonfigurasi via `settings.wa.daily_limit`). Panaskan nomor secara bertahap (lihat tips anti-ban di [user-guide.md](user-guide.md)).

---

## B. Setup Baileys (Jalur Non-Resmi — untuk testing)

Baileys adalah library open-source yang mengendalikan WhatsApp lewat protokol WhatsApp Web — **self-hosted dan 100% gratis**, tanpa limit pesan dari pihak ketiga. Tool ini menjalankannya sebagai sidecar (`baileys/server.js`, service `baileys` di docker-compose).

### Langkah-langkah

1. **Jalankan stack** — `docker compose up -d --build` (service `baileys` ikut jalan otomatis).
2. **Buka halaman QR** — di browser: `http://localhost:3001/qr`.
3. **Scan QR** memakai aplikasi WhatsApp di HP **nomor testing** (WhatsApp → Perangkat Tertaut → Tautkan Perangkat). Sesi tersimpan di volume `baileys_auth`, jadi tidak perlu scan ulang tiap restart.
4. **Cek status** — `http://localhost:3001/status` harus menunjukkan `"connected": true`.
5. Di tool, saat membuat campaign pilih provider **Non-resmi** — teks bebas bisa dikirim tanpa template approval, dan estimasi biaya di halaman review = Rp 0.

### Opsional: kunci API

Isi `BAILEYS_API_KEY` di `.env` (bebas, mis. string acak) untuk memproteksi endpoint kirim sidecar. Backend membaca key yang sama dari env — keduanya harus cocok. Bila dikosongkan, sidecar menerima tanpa key (hanya untuk jaringan lokal terpercaya).

### Endpoint sidecar (untuk referensi)

| Method | Path | Keterangan |
|---|---|---|
| GET | `/health` | `{ ok: true }` |
| GET | `/status` | `{ connected, qr_available, phone, uptime_seconds }` |
| GET | `/qr` | Halaman QR pairing (auto-refresh) |
| POST | `/send-text` | `{ to, text }` → `{ message_id }`; 409 bila belum terhubung |
| POST | `/logout` | Logout + hapus sesi (perlu scan QR ulang) |

---

## C. Perbandingan Resmi vs Non-Resmi

| Aspek | Resmi — Meta Cloud API | Non-resmi — Baileys (self-hosted) |
|---|---|---|
| **Biaya** | Rp 627,33/pesan marketing (ID); utility Rp 366,65 | **Rp 0** — tanpa limit pihak ketiga |
| **Setup** | Meta App + Business Manager + verifikasi bisnis + display name approve + nomor khusus + payment | `docker compose up` + scan QR di `localhost:3001/qr` |
| **Template** | **WAJIB** template approve Meta (marketing 48–72 jam) | **Teks bebas**, tanpa approval |
| **Limit** | 250 → 2.000 → 10.000 → 100.000 → unlimited per 24 jam | Tidak ada (tetap pakai throttling tool: delay 5–15 dtk) |
| **Throughput** | Sangat tinggi (~80 pesan/detik menurut sumber pihak ketiga) | Dibatasi throttling tool (sengaja, anti-ban) |
| **Status kirim** | Webhook resmi `delivered`/`read` + verifikasi signature | `sent` tercatat; delivered/read via webhook Meta saja |
| **Risiko** | Rendah bila opt-in & template benar | **Nomor bisa ke-banned WhatsApp** (jalur tidak resmi) |
| **Cocok untuk** | Blast produksi sungguhan | Testing template, variabel, dan AI-mapping |

## D. Kapan Pakai yang Mana

- **Testing** (coba template baru, cek render variabel, latih alur wizard, uji AI-mapping) → **non-resmi (Baileys)**. Gratis, tanpa menunggu approval template.
- **Blast produksi** (ke kontak/pelanggan asli) → **resmi (Meta Cloud API)**. Satu-satunya jalur yang aman dan legal untuk pengiriman massal.

Aturan di tool: validasi "template harus approved" hanya berlaku untuk jalur resmi; jalur non-resmi boleh mengirim teks bebas dari template mana pun.

## E. ⚠️ PERINGATAN TEGAS — Jangan Pakai Nomor Utama untuk Jalur Non-Resmi

> **JANGAN gunakan nomor WhatsApp utama/pribadi/bisnis Anda untuk jalur non-resmi (Baileys).**
>
> Jalur non-resmi bekerja di luar API resmi WhatsApp. WhatsApp secara aktif mendeteksi dan **mem-banned permanen** nomor yang terdeteksi memakai automasi tidak resmi — dan banned ini **tidak bisa dipulihkan**, termasuk riwayat chat Anda.
>
> Gunakan **nomor khusus testing** (nomor kedua / nomor baru) yang siap Anda relakan bila ter-banned. UI tool menampilkan peringatan eksplisit setiap kali Anda memilih provider non-resmi.
>
> Bahkan untuk nomor testing: jangan blast agresif, patuhi jeda kirim bawaan tool, dan hanya kirim ke nomor yang Anda kenal/kuasai.

### Aturan opt-in (berlaku untuk KEDUA jalur)

- Meta mewajibkan **persetujuan eksplisit (opt-in)** penerima sebelum pesan business-initiated dikirim: opt-in harus menyebut nama bisnis & channel WhatsApp, **tercatat** (bisa dibuktikan), dan mudah dicabut (mis. balas STOP).
- **Dilarang** memakai daftar nomor beli, hasil scraping, atau tebakan.
- Hormati opt-out segera — error `131050` berarti user menghentikan pesan marketing dari Anda.
- Spam → block/report massal → quality rating merah → limit dibekukan/diturunkan → template di-pause → nomor/WABA bisa di-suspend permanen.
