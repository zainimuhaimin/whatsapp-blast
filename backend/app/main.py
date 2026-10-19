"""
Entry point FastAPI tool blast WhatsApp.

Startup: create_all() (MVP, tanpa migrasi Alembic — lihat README),
seed user admin pertama dari ENV bila tabel users kosong,
seed default settings bila belum ada.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.api import api_router
from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.core.security import hash_password
from app.models import Base, Setting, User
from app.services import campaign_service

log = logging.getLogger(__name__)

app = FastAPI(title="WA Blast API", version="0.1.0")

origins = (
    [o.strip() for o in settings.FRONTEND_ORIGINS.split(",")]
    if settings.FRONTEND_ORIGINS != "*"
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health():
    return {"ok": True}


def _seed_admin() -> None:
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin = User(
                username=settings.ADMIN_USERNAME,
                password_hash=hash_password(settings.ADMIN_PASSWORD),
                is_active=True,
            )
            db.add(admin)
            db.commit()
            log.info("seed: user admin '%s' dibuat", settings.ADMIN_USERNAME)
    finally:
        db.close()


def _seed_settings() -> None:
    db = SessionLocal()
    try:
        for key, value in campaign_service.SETTING_DEFAULTS.items():
            if db.get(Setting, key) is None:
                db.add(Setting(key=key, value=value))
        db.commit()
    finally:
        db.close()


def _drop_legacy_recipient_unique() -> None:
    """
    DB lama (dibuat sebelum 2026-10-19) punya UNIQUE(campaign_id, phone) di
    campaign_recipients yang kini dihapus dari model agar satu nomor boleh
    menerima beberapa pesan berbeda dalam satu campaign. create_all() tidak
    menurunkan constraint, jadi hapus manual bila masih ada. Aman & idempoten.
    """
    from sqlalchemy import text
    db = SessionLocal()
    try:
        db.execute(text(
            "ALTER TABLE campaign_recipients "
            "DROP CONSTRAINT IF EXISTS campaign_recipients_campaign_id_phone_key"
        ))
        # Nama constraint bawaan Postgres untuk UniqueConstraint tanpa nama
        # eksplisit adalah {tabel}_{kolom1}_{kolom2}_key.
        db.commit()
    except Exception as exc:  # bukan Postgres / tabel belum ada -> abaikan
        db.rollback()
        log.debug("drop legacy unique dilewati (%s)", exc)
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    _drop_legacy_recipient_unique()
    _seed_admin()
    _seed_settings()
    log.info("startup selesai: tabel siap, seed admin & settings dicek")
