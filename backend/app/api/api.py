"""Agregator semua router di bawah prefix /api."""
from fastapi import APIRouter

from app.api.routers import (
    audit_logs,
    auth,
    campaigns,
    contacts,
    file_uploads,
    sender,
    settings,
    templates,
    test_numbers,
    webhooks,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(contacts.router)
api_router.include_router(templates.router)
api_router.include_router(campaigns.router)
api_router.include_router(file_uploads.router)
api_router.include_router(test_numbers.router)
api_router.include_router(settings.router)
api_router.include_router(audit_logs.router)
api_router.include_router(webhooks.router)
api_router.include_router(sender.router)

# Versi backend — naikkan setiap ada perubahan backend agar mudah
# memastikan backend yang berjalan sudah yang terbaru (lihat footer UI).
APP_VERSION = "2026-10-20b"


@api_router.get("/version", include_in_schema=False)
def api_version():
    return {"app": "wa-blast", "backend_version": APP_VERSION}
