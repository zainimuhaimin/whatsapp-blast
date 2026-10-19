"""
Task webhook: webhooks.handle_status_update (queue default).

Menerima payload callback status dari provider, lalu update
campaign_recipients (delivered/read) via provider_message_id.
Mendukung format Meta Cloud API; fallback format generik.
"""
import logging

from app.core.db import SessionLocal
from app.models import CampaignRecipient
from app.worker.celery_app import celery_app

log = logging.getLogger(__name__)

_VALID_STATUSES = {"delivered", "read", "sent", "failed"}


def _parse_meta(payload: dict) -> list[tuple[str, str]]:
    """Format Meta Cloud API: entry[].changes[].value.statuses[]."""
    out: list[tuple[str, str]] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            for st in value.get("statuses", []) or []:
                msg_id = st.get("id")
                status = st.get("status")
                if msg_id and status in _VALID_STATUSES:
                    out.append((msg_id, status))
    return out


def _parse_generic(payload: dict) -> list[tuple[str, str]]:
    """Fallback format generik: {"message_id"/"id", "status"}."""
    msg_id = payload.get("message_id") or payload.get("id")
    status = payload.get("status")
    if msg_id and status in _VALID_STATUSES:
        return [(str(msg_id), status)]
    return []


@celery_app.task(name="webhooks.handle_status_update")
def handle_status_update(payload: dict):
    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        updates = _parse_meta(payload) or _parse_generic(payload)
        applied = 0
        now = datetime.now(timezone.utc)
        for msg_id, status in updates:
            recipient = (
                db.query(CampaignRecipient)
                .filter(CampaignRecipient.provider_message_id == msg_id)
                .first()
            )
            if not recipient:
                log.info("webhook: provider_message_id %s tidak dikenal", msg_id)
                continue
            if status == "delivered":
                recipient.status = "delivered"
                recipient.delivered_at = now
            elif status == "read":
                recipient.status = "read"
                recipient.read_at = now
            elif status == "failed":
                recipient.status = "failed"
                recipient.last_error = str(payload.get("errors") or payload.get("error") or "webhook: failed")[:2000]
            applied += 1
        db.commit()
        return {"applied": applied, "total": len(updates)}
    finally:
        db.close()
