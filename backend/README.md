# WA Blast — Backend (FastAPI)

MVP tool blast WhatsApp dual-provider (resmi Meta Cloud API & non-resmi Baileys).

## Struktur

```
backend/
├── app/
│   ├── main.py                 # FastAPI app + startup (create_all, seed admin/settings)
│   ├── core/                   # config, security (JWT/bcrypt), db, deps, phone
│   ├── models/                 # 9 tabel SQLAlchemy sesuai ERD
│   ├── schemas/                # Pydantic request/response
│   ├── api/routers/            # auth, contacts, templates, campaigns,
│   │                           # test_numbers, settings, audit_logs, webhooks
│   ├── services/               # gemini_service, renderer, campaign_service,
│   │                           # rate_limiter, audit_service
│   ├── wa_adapter/             # base (interface), official_whatsapp, unofficial_baileys
│   └── worker/                 # celery_app + tasks (sender, campaigns, webhooks, maintenance)
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

## Menjalankan (Docker)

```bash
cd ~/workspace/wa-blast
cp backend/.env.example backend/.env   # lalu isi JWT_SECRET, ADMIN_PASSWORD, dsb.
docker compose up --build
```

- API: http://localhost:8000 (docs: `/docs`, health: `/health`)
- Worker: `celery -A app.worker.celery_app worker -Q wa_sender,default --concurrency=1`
- Beat: `celery -A app.worker.celery_app beat`

## Menjalankan lokal (tanpa Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://wa:wa@localhost:5432/wablast
export REDIS_URL=redis://localhost:6379/0
export JWT_SECRET=... ADMIN_USERNAME=admin ADMIN_PASSWORD=...
uvicorn app.main:app --reload
```

## Migrasi database

MVP ini memakai `Base.metadata.create_all()` saat startup (keputusan desain:
simpel, tanpa Alembic). Konsekuensi: perubahan skema setelah data produksi
ada harus ditangani manual (ALTER TABLE) atau reset DB. Lihat `ASUMSI.md`.

## Catatan penting

- Kredensial provider kosong -> adapter mode **dry-run** (tidak ada pesan
  sungguhan yang terkirim, hanya log warning).
- Jalur `official` wajib template berstatus `approved` sebelum campaign bisa
  di-confirm; jalur `unofficial` bebas template (untuk testing, pakai nomor
  khusus — bukan nomor utama).
- Lihat `ASUMSI.md` untuk daftar keputusan implementasi.
