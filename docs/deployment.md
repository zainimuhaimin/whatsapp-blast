# Deploy Produksi (VPS)

Panduan menjalankan WA Blast 24/7 di server publik (VPS) dengan akses
**Tailscale** (disarankan) atau **whitelist IP** + login aplikasi.
Semua langkah dalam Bahasa Indonesia.

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

## 2. Akses aplikasi: Tailscale (disarankan) vs whitelist IP

Installer menawarkan **dua mode akses** — pilih saat install:

### Mode 1 — Tailscale (disarankan)

VPS bergabung ke jaringan privat Tailscale Anda; aplikasi **hanya bisa dibuka
dari perangkat yang login ke akun Tailscale yang sama**. IP publik berubah,
CGNAT, pindah jaringan (WiFi ↔ data seluler) — semuanya tidak masalah, dan
tidak ada satu pun port yang terekspos ke internet publik.

**Persiapan (satu kali):**

1. Buat akun di **https://tailscale.com** (gratis, paket Personal).
2. Install aplikasi **Tailscale** di HP (iOS/Android) dan laptop, lalu **login
   dengan akun yang sama**.
3. Saat installer VPS berjalan, buka link login Tailscale yang muncul dan
   setujui perangkat `wablast`.

**Cara akses:** buka `http://<IP-Tailscale-VPS>/` dari HP/laptop Anda (IP-nya
ditampilkan di akhir install; atau pakai nama MagicDNS `wablast` di admin
console Tailscale), lalu login dengan akun admin aplikasi.

**Mengundang orang lain (2 cara):**

| Cara | Cocok untuk | Catatan |
|---|---|---|
| **Share mesin** — admin console → Machines → `wablast` → **Share…** | Kasih akses app ke orang tertentu | Orang itu hanya bisa melihat VPS `wablast`, **tidak** bisa melihat device lain di jaringan Anda. Dia perlu akun Tailscale sendiri. |
| **Invite ke tailnet** — admin console → **Invite** (via email) | Partner/anggota tim tetap | Paket gratis muat sampai **3 user**. |

Keduanya tetap harus **login ke aplikasi** (lapisan kedua) — share/invite
hanya mengatur siapa yang bisa mencapai servernya.

### Mode 2 — Whitelist IP publik

Firewall hanya mengizinkan satu IP publik Anda membuka port web.

- **MAC address tidak bisa dipakai** untuk whitelist via internet. MAC hanya
  hidup di jaringan lokal (layer 2) dan dibuang oleh router pertama — server
  di internet tidak pernah melihat MAC perangkat Anda.
- Cara cek IP publik: dari **perangkat & jaringan yang akan dipakai membuka
  aplikasi** (mis. HP di WiFi rumah), buka browser ke
  **https://ifconfig.me** atau **https://whatismyip.com** — catat alamat IPv4-nya.
- Cek ulang bila ganti jaringan (WiFi rumah ≠ data seluler — IP-nya beda).

#### IP statis vs dinamis (penting)

Kebanyakan ISP Indonesia memberi **IP dinamis** dan sering di belakang
**CGNAT** (satu IP publik dipakai rame-rame):

1. IP Anda bisa **berubah sewaktu-waktu** → whitelist harus diupdate
   (`bash deploy/update-whitelist.sh <IP-baru>`).
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
2. Menanyakan **mode akses** (Tailscale / whitelist IP), **username/password
   admin**, dan (opsional) API key Gemini.
3. Mode Tailscale: install Tailscale di VPS dan menghubungkannya ke akun Anda
   (buka link login yang muncul — satu kali saja).
4. Membuat rahasia acak (JWT secret, password database) di `backend/.env`
   — login aplikasi **AKTIF** (`AUTH_DISABLED=false`).
5. Mengaktifkan firewall: mode Tailscale → port web di-bind ke IP Tailscale VPS
   (publik tertutup total); mode whitelist IP → **port 80/443 hanya dari IP
   Anda** (aturan `ufw route`, karena port Docker diforward via NAT), SSH tetap
   terbuka.
6. Build & menjalankan seluruh stack (mode produksi).

Setelah selesai, buka aplikasi dari perangkat Anda lalu login dengan akun
admin yang baru dibuat:
- Mode Tailscale: `http://<IP-Tailscale-VPS>/` (ditampilkan di akhir install;
  perangkat harus login Tailscale dengan akun yang sama).
- Mode whitelist IP: `http://<IP-server-VPS>/` (dari jaringan yang IP-nya
  di-whitelist).

> **Catatan Baileys:** pairing WhatsApp tetap lewat menu **Koneksi WA** di
> aplikasi (QR ditampilkan di UI) — tidak perlu membuka port 3001.
> Tetap pakai **nomor testing**, bukan nomor utama.

## 4. Operasional

| Kebutuhan | Perintah (di folder repo, sebagai root) |
|---|---|
| Lihat log | `docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api` |
| Update aplikasi | `bash deploy/update.sh` |
| Ganti IP whitelist (mode 2) | `bash deploy/update-whitelist.sh <IP-baru>` |
| Lihat status Tailscale | `tailscale status` (di VPS) / admin console |
| Backup database | `docker compose exec postgres pg_dump -U wa wablast > backup-$(date +%F).sql` |
| Cek status | `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps` |

- **Cek versi backend** di footer sidebar aplikasi setelah update —
  pastikan angkanya naik (tanda backend baru yang jalan).
- **Jangan** menjalankan `docker-compose.yml` saja (tanpa override
  `docker-compose.prod.yml`) di server publik — itu mode lokal tanpa login.

## 5. Checklist keamanan

- [x] Login aplikasi AKTIF (dipaksa oleh override produksi)
- [x] Akses jaringan: mode Tailscale → port web hanya di-bind ke IP Tailscale
      (publik tertutup total); mode whitelist IP → firewall hanya mengizinkan
      IP Anda ke port web
- [x] Password database & JWT secret acak, tersimpan di file `.env` (chmod 600)
- [ ] SSH server diamankan (key-based auth; opsional: batasi port 22 ke IP Anda)
- [ ] Backup database berkala (cron `pg_dump` + simpan di luar server)
