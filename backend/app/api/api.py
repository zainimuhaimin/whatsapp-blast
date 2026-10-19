"""Agregator semua router di bawah prefix /api."""
from fastapi import APIRouter

from app.api.routers import (
    audit_logs,
    auth,
    campaigns,
    contacts,
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
api_router.include_router(test_numbers.router)
api_router.include_router(settings.router)
api_router.include_router(audit_logs.router)
api_router.include_router(webhooks.router)
api_router.include_router(sender.router)
