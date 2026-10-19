# ASUMSI — Frontend WA Blast (Vue 3 + Vite + Tailwind)

Dokumen ini mencatat keputusan & asumsi yang diambil saat membangun frontend MVP
di `~/workspace/wa-blast/frontend/`. Ditulis 2026-10-16.

## Stack & tooling

1. **Tailwind CSS v4** dipakai (bukan v3) — via plugin `@tailwindcss/vite` dan
   `@import "tailwindcss"` di `src/style.css`. Tidak ada `tailwind.config.js`.
2. **Tanpa Pinia** — state global (auth, toast) memakai modul ref-based sederhana
   di `src/stores/` (`useAuth.js`, `useToast.js`). Cukup untuk MVP single-user.
3. **Dockerfile: multi-stage Node build + nginx serve** (dipilih dibanding
   `vite preview`) karena nginx lebih cocok untuk image produksi: SPA fallback
   `try_files`, gzip, dan cache immutable untuk `/assets/`. Config ada di
   `frontend/nginx.conf`. `VITE_API_URL` di-inject sebagai build ARG.
4. **Tidak ada `docker-compose.yml` di frontend** — sesuai instruksi, compose
   dibuat agent backend di root repo.
5. **Bahasa Indonesia** di seluruh UI.

## Kontrak API (dari design/architecture-draft.md section 3)

6. Auth JWT via **httpOnly cookie** → axios selalu `withCredentials: true`.
   **401 → redirect ke `/login`** (interceptor di `src/api/client.js`).
7. Response list dinormalisasi oleh `unwrapPage()`: backend boleh mengembalikan
   array langsung atau object `{items, total, page, limit}` — keduanya didukung.
8. Payload review (`GET /api/campaigns/{id}/review`) dibaca secara defensif
   (`total_recipients|total`, `table|rows|recipients`, `samples|sample_messages`,
   `validation_errors|errors`, `duration_estimate_seconds|eta_seconds`,
   `cost_estimate`, `price_per_message`). Field yang belum disediakan backend
   dihitung di frontend sebagai fallback (lihat poin 9).
9. **Estimasi durasi & biaya (fallback frontend)**: `estimasi = penerima × 10 dtk`
   (rata-rata rentang 5–15 dtk, design section 4), dibatasi juga oleh
   `wa.rate_limit_per_hour` bila ada di settings. Tarif default per kategori
   (design section 6): marketing Rp 627,33 · utility Rp 366,65 ·
   authentication Rp 366,65 · service Rp 356,65. Bila backend sudah mengirim
   `cost_estimate`/`duration_estimate_seconds`, nilai backend yang dipakai.
10. **Estimasi biaya jalur unofficial selalu ditampilkan "Rp 0 (jalur gratis)"**
    (design section 7) — tidak dikali tarif.

## Alur wizard (section 1.3)

11. Campaign **dibuat saat user menekan "Lanjut" dari langkah 2** (template
    dipilih), dengan payload `{name, template_version_id, provider, is_test_mode,
    send_at}`. Catatan: kontrak `POST /api/campaigns` di design tidak memuat
    field `provider` — diasumsikan backend menerima/menyimpannya (default
    `official`); bila backend menolak, toast error akan muncul dan perlu
    penyesuaian backend.
12. `PUT /api/campaigns/{id}` dipakai untuk sinkronisasi info dasar bila user
    kembali ke langkah 1–2; kontrak design membatasi field update
    (`name`, `send_at`, `is_test_mode`) — diasumsikan `template_version_id` juga
    boleh di-update pada status `draft`. Kegagalan update tidak menghentikan wizard.
13. **Mapping default cerdas**: variabel bernama `*name*/*nama*` → field kontak
    `name`; `*phone*/*telp*/*nomor*` → `phone`; `*tag*` → `tag`; sisanya →
    nilai campaign dengan prefill hasil AI.
14. Langkah 5: blacklist dikecualikan (checkbox disabled + label
    "blacklist — dikecualikan"); backend juga diandalkan mem-skip via
    `POST /api/campaigns/{id}/recipients`. Mode test → `contact_ids: []`
    (backend memakai `test_numbers` aktif, sesuai kontrak).
15. Validasi `confirm` (jalur official wajib template `approved`, dst.)
    diasumsikan dikembalikan backend sebagai `validation_errors` di payload
    review — error ini **mengunci tombol konfirmasi** di UI.
16. "Jadwalkan" memanggil endpoint `confirm` yang sama; backend yang memutuskan
    status `scheduled` vs `queued` berdasarkan `send_at` (sesuai kontrak).

## Halaman lain

17. Dashboard mengambil `GET /api/campaigns/{id}/stats` per campaign (N+1
    request) — diterima untuk MVP; bila lambat, backend bisa menambahkan
    agregasi di response list.
18. Halaman detail campaign memakai **polling 15 detik** (stats + penerima)
    saat status `queued`/`sending`/`paused`.
19. Settings: value disimpan sebagai JSONB — editor otomatis menyesuaikan tipe
    (select/number/text/JSON) berdasarkan `KEY_META` untuk key yang dikenal
    (`wa.*`, `gemini.model`); key lain diedit sebagai JSON mentah.
20. Validasi nomor telepon di frontend: digit internasional 8–15 digit,
    leading `0` otomatis dikonversi ke `62`. Validasi final tetap di backend
    (disarankan library `phonenumbers`).

## Batasan yang disadari

- Frontend ini **hanya UI** — tidak ada pengiriman WhatsApp dari browser.
- Belum ada unit/E2E test; verifikasi = `npm run build` sukses.
- Daftar kontak langkah 5 wizard diambil dengan `limit=1000` sekaligus
  (tanpa pagination) demi UX checklist — untuk basis kontak >1000 perlu
  paginasi/search server-side di iterasi berikutnya.
