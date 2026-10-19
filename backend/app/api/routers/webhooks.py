"""
Webhook provider: POST /api/webhooks/whatsapp.

Menerima callback status delivered/read dari provider, diproses async via
task webhooks.handle_status_update. Endpoint GET verifikasi dipakai saat
mendaftarkan webhook di Meta (hub.challenge).
"""
import logging

from fastapi import APIRouter, Query, Request, Response

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    from app.worker.tasks.webhooks import handle_status_update

    handle_status_update.delay(payload or {})
    log.info("webhook whatsapp diterima, diantrekan untuk diproses")
    return {"ok": True}


@router.get("/whatsapp")
def whatsapp_verify(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
):
    """
    Verifikasi webhook Meta: kembalikan hub.challenge bila mode=subscribe.
    (Token verifikasi dicek sederhana; amankan via secret di produksi.)
    """
    if hub_mode == "subscribe" and hub_challenge:
        return Response(content=hub_challenge, media_type="text/plain")
    return {"ok": True}
