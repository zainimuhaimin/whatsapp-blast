# Deploy Produksi (VPS)

Panduan menjalankan WA Blast 24/7 di server publik (VPS) dengan akses
**whitelist IP** + login aplikasi. Semua langkah dalam Bahasa Indonesia.

> **Kenapa tidak di VM Muse?** VM yang dipakai agent ini tidak punya jalur
> masuk (ingress) publik — IP-nya internal di balik NAT, traffic keluar lewat
> proxy, dan VM bisa diganti sewaktu-waktu saat runtime di-update. Jadi tidak
> ada cara bagi HP/laptop Anda untuk membuka aplikasi yang berjalan di sana.
> VPS murah adalah host yang tepat untuk tool ini.

---

## 1. Siapkan VPS

Pilih salah satu (contoh harga 2026, bisa berubah):

| Opsi | Kisaran | Cocok untuk |
|---|---|---|
| VPS Indonesia (mis. penyedia lokal) | Rp 50–100rb/bln | Latensi kecil, bayar lokal |
| Oracle Cloud Free Tier (Ampere ARM) | Gratis (selamanya, kuota terbatas) | Paling hemat |
| Hetzner / Contabo / DigitalOcean | ±$5–6/bln | Stabil, dokumentasi bagus |

Spesifikasi minimum: **2 vCPU, 4 GB RAM, 20 GB disk**, Ubuntu **22.04 / 24.04**.
Setelah VPS aktif, catat **IP publik server** dari panel penyedia.

> **Batasan saya:** saya tidak pernah meminta/menyimpan password atau SSH key
> siapa pun (termasuk VPS Anda). Anda yang menjalankan perintah di server —
> saya pandu langkahnya.

## 2. Dapatkan IP publik Anda (untuk whitelist)

Whitelist memakai **IP publik**, bukan MAC address:

- **MAC address tidak bisa dipakai** untuk whitelist via internet. MAC hanya
  hidup di jaringan lokal (layer 2) dan dibuang oleh router pertama — server
  di internet tidak pernah melihat MAC perangkat Anda.
- Cara cek IP publik: dari **perangkat & jaringan yang akan dipakai membuka
  aplikasi** (mis. HP di WiFi rumah), buka browser ke
  **https://ifconfig.me** atau **https://whatismyip.com** — catat alamat IPv4-nya.
- Cek ulang bila ganti jaringan (WiFi rumah ≠ data seluler — IP-nya beda).

### IP statis vs dinamis (penting)

Kebanyakan ISP Indonesia memberi **IP dinamis** dan sering di belakang
**CGNAT** (satu IP publik dipakai rame-rame):

1. IP Anda bisa **berubah sewaktu-waktu** → whitelist harus diupdate
   (ada script 1 perintah: `bash deploy/update-whitelist.sh <IP-baru>`).
2. Kalau IP Anda CGNAT, whitelist IP itu juga membuka akses ke banyak
   pelanggan ISP lain yang kebetulan dapat IP sama. Risiko ini **ditutup oleh
   lapisan kedua: login aplikasi** (wajib aktif di produksi).

Pilihan terbaik: minta **IP statis** ke ISP (biasanya add-on berbayar) atau
pakai VPN dengan IP dedicated. Kalau belum ada, IP dinamis + script update
tetap bisa dipakai — cuma perlu update manual tiap IP berubah.

## 3. Install di VPS

SSH ke server Anda (dari laptop), lalu:

```bash
git clone https://github.com/zainimuhaimin/whatsapp-blast.git
cd whatsapp-blast
sudo bash deploy/install.sh
```

Script akan:
1. Install Docker (bila belum ada).
2. Menanyakan **IP whitelist Anda**, **username/password admin**, dan
   (opsional) API key Gemini.
3. Membuat rahasia acak (JWT secret, password database) di `backend/.env`
   — login aplikasi **AKTIF** (`AUTH_DISABLED=false`).
4. Mengaktifkan firewall: **port 80/443 hanya dari IP whitelist Anda**,
   port lain tertutup, SSH tetap terbuka.
5. Build & menjalankan seluruh stack (mode produksi).

Setelah selesai, buka **`http://<IP-server-VPS>/`** dari jaringan yang
IP-nya di-whitelist, lalu login dengan akun admin yang baru dibuat.

> **Catatan Baileys:** pairing WhatsApp tetap lewat menu **Koneksi WA** di
> aplikasi (QR ditampilkan di UI) — tidak perlu membuka port 3001.
> Tetap pakai **nomor testing**, bukan nomor utama.

## 4. Operasional

| Kebutuhan | Perintah (di folder repo, sebagai root) |
|---|---|
| Lihat log | `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api` |
| Update aplikasi | `bash deploy/update.sh` |
| Ganti IP whitelist | `bash deploy/update-whitelist.sh <IP-baru>` |
| Backup database | `docker compose exec postgres pg_dump -U wa wablast > backup-$(date +%F).sql` |
| Cek status | `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps` |

- **Cek versi backend** di footer sidebar aplikasi setelah update —
  pastikan angkanya naik (tanda backend baru yang jalan).
- **Jangan** menjalankan `docker-compose.yml` saja (tanpa override
  `docker-compose.prod.yml`) di server publik — itu mode lokal tanpa login.

## 5. Checklist keamanan

- [x] Login aplikasi AKTIF (dipaksa oleh override produksi)
- [x] Firewall: hanya IP whitelist yang bisa membuka port web
- [x] Password database & JWT secret acak, tersimpan di file `.env` (chmod 600)
- [ ] SSH server diamankan (key-based auth; opsional: batasi port 22 ke IP Anda)
- [ ] Backup database berkala (cron `pg_dump` + simpan di luar server)
