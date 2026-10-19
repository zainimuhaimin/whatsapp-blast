# Panduan Pengguna

Panduan langkah-demi-langkah memakai Tool Blast WhatsApp — dari menyiapkan kontak sampai memantau hasil kirim. Ditulis untuk pengguna non-teknis; tidak perlu paham koding.

---

## Alur Singkat

**Kontak → Template → Campaign → Input AI → Mapping Variabel → Review & Konfirmasi → Kirim → Pantau**

Setiap blast selalu melewati **halaman review & konfirmasi** — tidak ada pesan yang terkirim tanpa Anda menyetujuinya dulu.

---

## 1. Kelola Kontak

Buka menu **Kontak**. Kontak diinput **manual** — tool ini tidak mengambil kontak dari mana pun.

- **Tambah kontak:** isi *Nama*, *Nomor HP* (format internasional tanpa tanda +, mis. `6281234567890`), lalu opsional *Tag* (mis. `pelanggan-lama`, `reseller`) dan *Catatan*.
- **Tag** berguna untuk segmentasi: saat membuat campaign Anda bisa memilih hanya kontak dengan tag tertentu.
- **Blacklist (opt-out):** bila seseorang minta berhenti menerima pesan (mis. membalas "STOP"), aktifkan blacklist pada kontaknya. Kontak yang di-blacklist **otomatis dikecualikan** dari semua blast berikutnya — Anda tidak perlu menghapusnya.
- **Jangan hapus kontak** yang sudah pernah dipakai di campaign; gunakan blacklist untuk menonaktifkan.

> **Etika opt-in (penting):** hanya blast ke orang yang **sudah memberi izin eksplisit** menerima pesan WhatsApp dari bisnis Anda — misalnya pelanggan yang mencentang persetujuan saat checkout, atau peserta yang mendaftar lewat formulir. Dilarang memakai daftar nomor beli, hasil scraping, atau tebakan. Izin harus tercatat dan mudah dicabut (balas STOP). Melanggar ini bisa membuat nomor bisnis Anda di-banned permanen oleh WhatsApp (lihat juga [providers.md](providers.md)).

## 2. Buat Template

Buka menu **Template**, lalu buat baru.

- **Nama template** — nama internal, mis. `Promo Ramadhan 2026`.
- **Isi pesan (body)** — tulis pesan dengan **variabel** diapit kurung kurawal ganda, contoh:

```
Halo {{nama}}! 🌙

{{promo}}

Gunakan kode *{{kode}}* saat checkout ya.
```

Variabel yang tersedia akan **terdeteksi otomatis** dari body (pada contoh di atas: `nama`, `promo`, `kode`).

- Aturan nama variabel: huruf, angka, dan underscore saja; diawali huruf/underscore (contoh benar: `{{nama}}`, `{{kode_promo}}`; contoh salah: `{{1nama}}`, `{{kode-promo}}`).
- Setiap kali Anda **mengedit isi pesan**, sistem membuat **versi baru** (versi lama tidak berubah). Campaign selalu memakai versi yang "ter-pin" saat campaign dibuat, jadi campaign lama tidak ikut berubah bila template diedit kemudian.
- **Khusus jalur resmi (Meta Cloud API):** template harus **terdaftar & di-approve Meta** sebelum bisa dipakai blast (prosesnya bisa hitungan jam sampai 2–3 hari untuk kategori marketing). Lihat [providers.md](providers.md) untuk cara mendaftarkannya.

## 3. Buat Campaign

Buka menu **Campaign** → **Campaign Baru**, lalu ikuti wizard:

1. **Nama campaign** — mis. `Blast Promo Ramadhan - Gelombang 1`.
2. **Pilih template** (versi yang ter-pin).
3. **Pilih provider:**
   - **Resmi** — untuk blast produksi sungguhan (berbayar per pesan, lihat [providers.md](providers.md)).
   - **Non-resmi (Baileys)** — untuk testing; **jangan pakai nomor WA utama/pribadi Anda** (risiko banned — baca peringatan di [providers.md](providers.md)).
4. **Mode test (opsional):** aktifkan untuk latihan — pesan hanya dikirim ke nomor test terdaftar, bukan ke kontak asli. Banner jelas akan tampil di UI agar tidak tertukar.
5. **Jadwalkan (opsional):** isi tanggal & jam kirim untuk blast terjadwal; kosongkan untuk kirim segera setelah konfirmasi.
6. **Pilih penerima:** centang kontak (bisa filter per tag). Kontak yang di-blacklist otomatis tidak muncul. Nomor duplikat otomatis dilewati.

## 4. Input AI — Isi Variabel Secara Otomatis

> **Setup sekali di awal:** buka menu **Pengaturan → 🤖 AI — Google Gemini**.
> Ambil API key gratis di [Google AI Studio](https://aistudio.google.com/apikey) (klik *Get API Key*),
> tempel di kolom API Key, pilih model (mis. `gemini-2.5-flash`), lalu klik **🔌 Test koneksi**
> untuk memastikan key valid. Key tersimpan aman — tidak pernah ditampilkan utuh.

Di langkah ini Anda cukup menulis **teks bebas** berisi info campaign, lalu AI (Google Gemini) mengekstrak nilai tiap variabel. Hasilnya **selalu bisa Anda edit manual** sebelum lanjut.

**Contoh konkret:**

Template Anda punya variabel: `nama`, `promo`, `kode`.

Anda menulis di kolom input AI:

> "Promo Ramadhan: diskon 30% untuk semua serum wajah, berlaku sampai 30 April 2026. Kode promonya RAMADHAN30. Info lebih lanjut hubungi admin."

AI mengekstrak:

| Variabel | Hasil AI |
|---|---|
| `promo` | diskon 30% untuk semua serum wajah, berlaku sampai 30 April 2026 |
| `kode` | RAMADHAN30 |

`nama` tidak diisi AI — karena nama tiap penerima berbeda, ia diambil dari data kontak (lihat langkah mapping di bawah).

**Penting:** AI hanya mengisi variabel yang nilainya **sama untuk semua penerima** (seperti isi promo). AI **tidak akan pernah** mengarang data personal penerima — itu selalu datang dari database kontak Anda.

## 5. Mapping Variabel

Di langkah ini Anda menentukan **sumber** tiap variabel — ada dua pilihan:

| Sumber | Artinya | Contoh |
|---|---|---|
| **Kontak** | Diambil dari data tiap penerima (berbeda-beda) | `nama` → field *Nama* kontak; bisa juga *Nomor HP* atau *Tag* |
| **Campaign** | Satu nilai berlaku untuk semua penerima (hasil AI di langkah 4, bisa diedit) | `promo`, `kode` |

Atur mapping untuk semua variabel sampai tidak ada yang kosong. Pesan untuk tiap penerima kemudian **di-render otomatis**: `Halo {{nama}}!` menjadi `Halo Budi!`, `Halo Sari!`, dan seterusnya.

## 6. Review & Konfirmasi — Periksa Sebelum Blast

Ini halaman terpenting: **baca semuanya sebelum menekan tombol KONFIRM & BLAST.** Elemen-elemennya:

| Elemen | Yang harus Anda cek |
|---|---|
| **Total penerima** | Jumlah kontak yang akan dikirimi. Pastikan angkanya masuk akal (tidak ada yang ke-blast dua kali atau kontak yang seharusnya dikecualikan). |
| **Tabel penerima × nilai variabel** | Daftar tiap penerima beserta nilai variabel yang akan diterimanya. Spot-check beberapa baris: apakah nama cocok dengan nomornya? Apakah tidak ada yang kosong/aneh? |
| **Sample pesan ter-render** | 5 contoh pesan final persis seperti yang akan diterima. Baca baik-baik: ejaan, kode promo, dan link. |
| **Estimasi durasi** | Perkiraan waktu pengiriman (sistem mengirim berurutan dengan jeda 5–15 detik + batas per jam). Blast 500 kontak bisa memakan waktu ~1–2 jam — rencanakan jam kirimnya. |
| **Estimasi biaya** (jalur resmi) | Total biaya = jumlah penerima × tarif kategori template (mis. marketing ≈ Rp 627,33/pesan → 500 kontak ≈ Rp 314 rb). Untuk jalur non-resmi: Rp 0 (tampilkan sisa kuota bila tersedia). |
| **Daftar error validasi** | Bila ada masalah (mis. variabel belum dipetakan, template belum di-approve Meta, jumlah penerima melebihi limit harian nomor), daftarnya muncul di sini dan tombol konfirmasi **tidak bisa** ditekan sampai diperbaiki. |

Bila semuanya benar → tekan **KONFIRM & BLAST**. Campaign berstatus `queued` (kirim segera) atau `scheduled` (terjadwal), lalu worker mulai mengirim satu per satu.

## 7. Monitoring — Pantau Hasil Kirim

Buka detail campaign untuk melihat:

- **Ringkasan status:** berapa `pending` (antri), `sent` (terkirim ke provider), `delivered` (sampai ke HP penerima), `read` (dibaca), `failed` (gagal).
- **Tabel per penerima:** status tiap nomor + pesan error terakhir bila gagal. Pesan gagal akan **di-retry otomatis** (maks 3x dengan jeda makin lama: 5 menit → 30 menit → 2 jam).
- **Kontrol:** **Pause** untuk menjeda, **Resume** untuk lanjut, **Cancel** untuk membatalkan (sisa yang belum terkirim tidak jadi dikirim).

## 8. Nomor Test (Test Numbers)

Menu **Test Numbers**: daftarkan nomor HP Anda sendiri / tim (mis. label "HP saya"). Gunakan bersama **Mode test** pada campaign untuk:

- mencoba template baru sebelum blast sungguhan,
- memastikan variabel ter-render benar,
- melatih alur tanpa risiko mengganggu kontak asli.

Selalu uji ke nomor test dulu untuk campaign penting.

---

## Tips Anti-Banned

1. **Hanya kirim ke yang sudah opt-in** — ini aturan nomor satu WhatsApp/Meta. Daftar beli/scrape = jalan tercepat menuju banned.
2. **Jangan pakai nomor pribadi untuk jalur non-resmi** — gunakan nomor khusus testing (peringatan lengkap di [providers.md](providers.md)).
3. **Panaskan nomor baru:** mulai dari pesan ke nomor sendiri → batch kecil → baru blast besar. Jangan habiskan limit 250 pesan di hari pertama.
4. **Hormati opt-out secepatnya** — blacklist kontak yang minta berhenti, jangan kirim lagi.
5. **Kirim di jam wajar** dan segmentasikan target (blast tersegmentasi 500 orang lebih aman & efektif daripada 5.000 membabi buta).
6. **Satu template = satu tujuan** — jangan selundupkan promo di template kategori utility; Meta bisa mengubah kategorinya dan menurunkan rating kualitas Anda.
7. **Throttling sudah otomatis** (jeda acak 5–15 detik, maks ~300 pesan/jam) — jangan mencoba mengakali dengan menambah worker.
8. **Jaga kualitas:** banyak block/report dari penerima → limit diturunkan → template di-pause → akun bisa di-suspend permanen.

---

## Install sebagai Aplikasi HP (PWA)

WA Blast bisa di-install sebagai aplikasi di HP (Android & iPhone) — tampil fullscreen seperti aplikasi asli, ada ikon di home screen, dan bisa dibuka tanpa mengetik alamat.

**Android (Chrome):** buka alamat WA Blast → menu ⋮ → **"Install app"** / **"Tambahkan ke Layar utama"** → Install.

**iPhone (Safari):** buka alamat WA Blast → tombol Share → **"Add to Home Screen"** → Add.

Catatan: aplikasi tetap butuh koneksi ke server (data campaign, kontak, dsb. diambil live dari backend). Yang di-install adalah tampilan aplikasinya; service worker hanya mempercepat loading aset statis dan tidak pernah menyimpan data API.

## Tampilan Mobile

Navigasi di HP: tombol menu (☰) di kiri atas membuka seluruh menu. Tabel otomatis berubah menjadi daftar dua baris agar mudah dibaca di layar kecil. Wizard campaign bisa dioperasikan penuh dari HP — tombol Lanjut/Kembali menempel di bawah layar.
