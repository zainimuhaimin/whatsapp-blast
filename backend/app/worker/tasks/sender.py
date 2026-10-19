"""
Task pengirim utama: sender.dispatch_campaign (queue wa_sender, concurrency 1).

Idempotent: hanya memproses penerima berstatus 'pending', aman di-restart.
Alur per penerima: render -> cek token bucket -> kirim via adapter ->
update status/provider_message_id -> sleep acak 5-15 dtk.
Berhenti bila campaign di-pause/cancel. Retry gagal: +5 mnt / +30 mnt / +2 jam,
maks 3x lalu failed final.
"""
import logging
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

from app.core.db import SessionLocal, get_redis
from app.models import Campaign, CampaignRecipient
from app.services import campaign_service, rate_limiter, renderer
from app.wa_adapter.base import get_adapter
from app.worker.celery_app import celery_app

log = logging.getLogger(__name__)

# Backoff retry: gagal ke-1 -> +5 mnt, ke-2 -> +30 mnt, ke-3 -> +2 jam
RETRY_BACKOFF_SECONDS = [300, 1800, 7200]
MAX_RETRIES = 3


def _now():
    return datetime.now(timezone.utc)


@celery_app.task(name="sender.dispatch_campaign", queue="wa_sender", bind=True)
def dispatch_campaign(self, campaign_id: str):
    db = SessionLocal()
    redis_client = get_redis()
    try:
        try:
            cid = uuid.UUID(campaign_id)
        except ValueError:
            log.error("dispatch_campaign: campaign_id tidak valid: %s", campaign_id)
            return {"skipped": True}

        campaign = db.get(Campaign, cid)
        if not campaign:
            log.error("dispatch_campaign: campaign %s tidak ditemukan", campaign_id)
            return {"skipped": True}
        if campaign.status not in ("queued", "sending"):
            log.info("dispatch_campaign: campaign %s status '%s', dilewati",
                     campaign_id, campaign.status)
            return {"skipped": True}

        campaign.status = "sending"
        if not campaign.started_at:
            campaign.started_at = _now()
        db.commit()

        adapter = get_adapter(campaign.provider)
        settings_map = campaign_service.get_settings_map(db)
        delay_min = float(settings_map.get("wa.delay_min_sec", 5) or 5)
        delay_max = float(settings_map.get("wa.delay_max_sec", 15) or 15)
        rate_limit = int(settings_map.get("wa.rate_limit_per_hour", 300) or 300)
        bucket_key = f"wa:ratelimit:{campaign.provider}"
        version = campaign.template_version

        sent = 0
        while True:
            # Cek status campaign terbaru; berhenti bila pause/cancel
            db.refresh(campaign)
            if campaign.status in ("paused", "cancelled"):
                log.info("dispatch_campaign: campaign %s berhenti (status %s)",
                         campaign_id, campaign.status)
                break

            recipient = (
                db.query(CampaignRecipient)
                .filter(
                    CampaignRecipient.campaign_id == cid,
                    CampaignRecipient.status == "pending",
                )
                .order_by(CampaignRecipient.created_at)
                .first()
            )
            if not recipient:
                break  # tidak ada lagi yang pending

            values = campaign_service.resolve_values(db, campaign, recipient)

            # Pengaman: nomor yang tidak punya data sama sekali (tidak masuk
            # dari input AI, tidak ter-resolve via mapping/kontak) dilewati —
            # jangan kirim pesan kosong yang bikin error.
            template_vars = version.variables or []
            if template_vars and not any(
                (values.get(v) or "").strip() for v in template_vars
            ):
                recipient.status = "skipped"
                recipient.last_error = (
                    "dilewati: tidak ada nilai variabel untuk nomor ini "
                    "(tidak dari input AI / mapping)"
                )
                db.commit()
                continue

            # Token bucket: bila habis, jadwalkan ulang task 60 dtk kemudian
            if not rate_limiter.acquire(redis_client, bucket_key, rate_limit):
                log.info("dispatch_campaign: rate limit habis, dijadwalkan ulang")
                dispatch_campaign.apply_async(args=[campaign_id], countdown=60)
                return {"requeued": True, "reason": "rate_limit"}

            try:
                if campaign.provider == "official":
                    template_name = (
                        version.provider_template_name or version.template.name
                    )
                    resp = adapter.send_template(
                        recipient.phone, template_name, "id", values
                    )
                else:
                    text = renderer.render(version.body, values)
                    resp = adapter.send_text(recipient.phone, text)
                recipient.status = "sent"
                recipient.sent_at = _now()
                recipient.provider_message_id = resp.get("provider_message_id")
                recipient.last_error = None
                sent += 1
            except Exception as exc:  # kirim gagal -> catat + jadwal retry
                recipient.retry_count += 1
                recipient.last_error = str(exc)[:2000]
                recipient.status = "failed"
                if recipient.retry_count >= MAX_RETRIES:
                    recipient.next_retry_at = None  # failed final
                    log.warning("dispatch_campaign: %s gagal final: %s",
                                recipient.phone, exc)
                else:
                    backoff = RETRY_BACKOFF_SECONDS[recipient.retry_count - 1]
                    recipient.next_retry_at = _now() + timedelta(seconds=backoff)
                    log.info("dispatch_campaign: %s gagal, retry dalam %ss: %s",
                             recipient.phone, backoff, exc)
            db.commit()

            # Jeda acak antar pesan (anti-ban)
            time.sleep(random.uniform(delay_min, delay_max))

        # Finalisasi: completed bila tidak ada pending / failed yang masih bisa retry
        db.refresh(campaign)
        remaining = (
            db.query(CampaignRecipient)
            .filter(
                CampaignRecipient.campaign_id == cid,
                CampaignRecipient.status.in_(["pending", "failed"]),
            )
            .count()
        )
        retryable = (
            db.query(CampaignRecipient)
            .filter(
                CampaignRecipient.campaign_id == cid,
                CampaignRecipient.status == "failed",
                CampaignRecipient.retry_count < MAX_RETRIES,
                CampaignRecipient.next_retry_at.isnot(None),
            )
            .count()
        )
        if campaign.status == "sending" and remaining == 0:
            campaign.status = "completed"
            campaign.finished_at = _now()
            db.commit()
        log.info("dispatch_campaign selesai: campaign=%s terkirim=%s", campaign_id, sent)
        return {"sent": sent, "retryable_failed": retryable}
    finally:
        db.close()
