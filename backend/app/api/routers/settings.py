"""
Settings: baca semua konfigurasi operasional, update satu key (whitelist saja).
Secret (API key/token) via ENV, bukan DB.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import Setting, User
from app.schemas import SettingOut, SettingUpdate
from app.services import campaign_service
from app.services.audit_service import write_audit

router = APIRouter(prefix="/settings", tags=["settings"])

# Whitelist key yang boleh diubah via API (bukan secret)
ALLOWED_KEYS = {
    "wa.provider",
    "wa.rate_limit_per_hour",
    "wa.delay_min_sec",
    "wa.delay_max_sec",
    "wa.price_per_message_idr",
    "wa.daily_limit",
    "gemini.model",
}


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=list[SettingOut])
def list_settings(db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    merged = campaign_service.get_settings_map(db)
    return [SettingOut(key=k, value=v) for k, v in sorted(merged.items())]


@router.put("/{key}", response_model=SettingOut)
def update_setting(key: str, payload: SettingUpdate, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    if key not in ALLOWED_KEYS:
        raise HTTPException(
            status_code=403,
            detail=f"key '{key}' tidak boleh diubah via API (bukan whitelist)",
        )
    row = db.get(Setting, key)
    old_value = row.value if row else campaign_service.SETTING_DEFAULTS.get(key)
    if row:
        row.value = payload.value
    else:
        row = Setting(key=key, value=payload.value)
        db.add(row)
    db.commit()
    write_audit(db, "settings.update", user_id=user.id, entity_type="setting",
                entity_id=key,
                metadata={"old": old_value, "new": payload.value}, ip_address=_ip(request))
    return SettingOut(key=key, value=payload.value)
