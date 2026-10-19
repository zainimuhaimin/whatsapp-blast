"""
Sender: status koneksi & pairing jalur non-resmi (Baileys sidecar).

- GET  /sender/status     -> status koneksi sidecar (proxy)
- GET  /sender/qr-data    -> string QR mentah untuk pairing (proxy)
- POST /sender/disconnect -> logout sidecar + hapus sesi (perlu scan QR ulang)

Jalur resmi (Meta Cloud API) tidak butuh pairing — statusnya hanya info
apakah kredensial terkonfigurasi.
"""
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import User
from app.services.audit_service import write_audit
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

router = APIRouter(prefix="/sender", tags=["sender"])


def _base_url() -> str | None:
    url = (settings.BAILEYS_API_URL or "").strip().rstrip("/")
    return url or None


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if settings.BAILEYS_API_KEY:
        headers["x-api-key"] = settings.BAILEYS_API_KEY
    return headers


def _proxy_get(path: str) -> dict | None:
    """GET ke sidecar; kembalikan dict atau None bila tak terjangkau."""
    base = _base_url()
    if not base:
        return None
    try:
        with httpx.Client(timeout=10, trust_env=False) as client:
            resp = client.get(base + path, headers=_headers())
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        log.warning("sidecar %s tak terjangkau (%s)", path, exc)
        return None


@router.get("/status")
def sender_status(db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    base = _base_url()
    if not base:
        return {
            "configured": False,
            "reachable": False,
            "connected": False,
            "dry_run": True,
            "phone": None,
            "uptime_seconds": 0,
            "qr_available": False,
            "note": "BAILEYS_API_URL belum diisi — pengiriman jalur non-resmi berjalan sebagai dry-run.",
        }
    data = _proxy_get("/status")
    if data is None:
        return {
            "configured": True,
            "reachable": False,
            "connected": False,
            "dry_run": False,
            "phone": None,
            "uptime_seconds": 0,
            "qr_available": False,
            "note": "Sidecar Baileys tidak terjangkau. Pastikan service baileys berjalan.",
        }
    return {
        "configured": True,
        "reachable": True,
        "connected": bool(data.get("connected")),
        "dry_run": False,
        "phone": data.get("phone"),
        "uptime_seconds": data.get("uptime_seconds") or 0,
        "qr_available": bool(data.get("qr_available")),
        "note": None,
    }


@router.get("/qr-data")
def sender_qr_data(db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    data = _proxy_get("/qr-data")
    if data is None:
        raise HTTPException(status_code=502,
                            detail="Sidecar Baileys tidak terjangkau.")
    return {"qr": data.get("qr"), "connected": bool(data.get("connected")),
            "phone": data.get("phone")}


@router.post("/disconnect")
def sender_disconnect(request: Request, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    base = _base_url()
    if not base:
        raise HTTPException(status_code=409,
                            detail="BAILEYS_API_URL belum dikonfigurasi.")
    try:
        with httpx.Client(timeout=15, trust_env=False) as client:
            resp = client.post(base + "/logout", headers=_headers())
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502,
                            detail=f"Gagal memutus koneksi: {exc.response.text[:200]}")
    except Exception as exc:
        raise HTTPException(status_code=502,
                            detail=f"Sidecar tak terjangkau: {exc}")
    write_audit(db, "sender.disconnect", user_id=user.id,
                entity_type="sender", entity_id="baileys",
                metadata={}, ip_address=request.client.host if request.client else None)
    return JSONResponse({"ok": True, "detail": "Koneksi diputus. Scan QR ulang untuk pairing kembali."})
