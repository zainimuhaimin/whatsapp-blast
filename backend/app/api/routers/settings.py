"""
Settings: baca semua konfigurasi operasional, update satu key (whitelist saja).

API key Gemini BISA diatur via UI (disimpan di DB) — tapi tidak pernah
dikembalikan utuh via API (hanya pratinjau tersamar), dan tidak pernah
ditulis ke audit log.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings as env_settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import Setting, User
from app.schemas import SettingOut, SettingUpdate
from app.services import campaign_service
from app.services.audit_service import write_audit

router = APIRouter(prefix="/settings", tags=["settings"])

# Whitelist key yang boleh diubah via API
ALLOWED_KEYS = {
    "wa.provider",
    "wa.rate_limit_per_hour",
    "wa.delay_min_sec",
    "wa.delay_max_sec",
    "wa.price_per_message_idr",
    "wa.daily_limit",
    "gemini.model",
    "gemini.api_key",
}

# Key rahasia: tidak pernah dikembalikan utuh & tidak masuk audit log
SECRET_KEYS = {"gemini.api_key"}


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _mask_secret(value: object) -> str:
    """Pratinjau tersamar: '••••' + 4 karakter terakhir, atau '' bila kosong."""
    s = str(value or "")
    if not s:
        return ""
    return "••••••" + s[-4:] if len(s) > 4 else "••••••"


def _resolve_gemini(db: Session) -> tuple[str, str, str]:
    """
    Ambil (api_key, model, sumber). Sumber: 'pengaturan' bila diisi via UI,
    'environment' bila fallback ke ENV.
    """
    db_key = str(campaign_service.get_setting(db, "gemini.api_key") or "")
    if db_key:
        api_key, source = db_key, "pengaturan"
    else:
        api_key, source = env_settings.GEMINI_API_KEY or "", "environment"
    model = str(
        campaign_service.get_setting(db, "gemini.model")
        or env_settings.GEMINI_MODEL
        or "gemini-2.0-flash"
    )
    return api_key, model, source


@router.get("", response_model=list[SettingOut])
def list_settings(db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    merged = campaign_service.get_settings_map(db)
    out = []
    for k in sorted(merged):
        v = merged[k]
        if k in SECRET_KEYS:
            out.append(SettingOut(key=k, value=_mask_secret(v), is_secret=True))
        else:
            out.append(SettingOut(key=k, value=v))
    return out


@router.post("/gemini/test")
def test_gemini_connection(request: Request,
                           db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    """
    Test koneksi ke Gemini memakai API key & model yang sedang efektif.
    Mengirim satu prompt minimal ("ping") — tidak memakai kuota berarti.
    """
    api_key, model_name, source = _resolve_gemini(db)
    if not api_key:
        write_audit(db, "settings.gemini_test", user_id=user.id,
                    entity_type="setting", entity_id="gemini",
                    metadata={"ok": False, "error": "api_key_belum_diatur"},
                    ip_address=_ip(request))
        return {"ok": False, "model": model_name, "source": source,
                "error": "API key belum diatur — isi di Pengaturan → AI."}
    try:
        import google.generativeai as genai
    except ImportError:
        return {"ok": False, "model": model_name, "source": source,
                "error": "package google-generativeai belum terinstall di server"}
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name=model_name)
        resp = model.generate_content("Balas hanya dengan satu kata: ok")
        reply = (getattr(resp, "text", "") or "").strip()[:200]
        write_audit(db, "settings.gemini_test", user_id=user.id,
                    entity_type="setting", entity_id="gemini",
                    metadata={"ok": True, "model": model_name, "source": source},
                    ip_address=_ip(request))
        return {"ok": True, "model": model_name, "source": source, "reply": reply}
    except Exception as exc:
        write_audit(db, "settings.gemini_test", user_id=user.id,
                    entity_type="setting", entity_id="gemini",
                    metadata={"ok": False, "model": model_name, "source": source},
                    ip_address=_ip(request))
        return {"ok": False, "model": model_name, "source": source,
                "error": str(exc)[:300]}


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
    # audit: nilai secret tidak pernah ditulis (hanya pratinjau tersamar)
    if key in SECRET_KEYS:
        meta = {"new": _mask_secret(payload.value)}
    else:
        meta = {"old": old_value, "new": payload.value}
    write_audit(db, "settings.update", user_id=user.id, entity_type="setting",
                entity_id=key, metadata=meta, ip_address=_ip(request))
    out_value = _mask_secret(payload.value) if key in SECRET_KEYS else payload.value
    return SettingOut(key=key, value=out_value, is_secret=key in SECRET_KEYS)
