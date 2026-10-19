"""
Task queue default: campaigns.enqueue_due, campaigns.retry_due.
"""
import logging
import uuid
from datetime import datetime, timezone

from app.core.db import SessionLocal
from app.models import Campaign, CampaignRecipient
from app.worker.celery_app import celery_app

log = logging.getLogger(__name__)
MAX_RETRIES = 3


def _now():
    return datetime.now(timezone.utc)


@celery_app.task(name="campaigns.enqueue_due")
def enqueue_due():
    """Beat tiap 1 menit: campaign 'scheduled' yang send_at-nya tiba -> queued + dispatch."""
    db = SessionLocal()
    try:
        now = _now()
        due = (
            db.query(Campaign)
            .filter(Campaign.status == "scheduled", Campaign.send_at <= now)
            .all()
        )
        for campaign in due:
            campaign.status = "queued"
            db.commit()
            from app.worker.tasks.sender import dispatch_campaign

            dispatch_campaign.delay(str(campaign.id))
            log.info("enqueue_due: campaign %s dijadwalkan -> queued", campaign.id)
        return {"enqueued": len(due)}
    finally:
        db.close()


@celery_app.task(name="campaigns.retry_due")
def retry_due():
    """
    Beat tiap 5 menit: recipient 'failed' dengan retry_count < 3 dan
    next_retry_at <= now -> kembalikan ke 'pending', lalu trigger dispatch.
    """
    db = SessionLocal()
    try:
        now = _now()
        due = (
            db.query(CampaignRecipient)
            .filter(
                CampaignRecipient.status == "failed",
                CampaignRecipient.retry_count < MAX_RETRIES,
                CampaignRecipient.next_retry_at <= now,
            )
            .all()
        )
        campaign_ids: set[uuid.UUID] = set()
        for recipient in due:
            recipient.status = "pending"
            recipient.next_retry_at = None
            campaign_ids.add(recipient.campaign_id)
        db.commit()

        from app.worker.tasks.sender import dispatch_campaign

        triggered = 0
        for cid in campaign_ids:
            campaign = db.get(Campaign, cid)
            if campaign and campaign.status in ("queued", "sending", "scheduled", "paused"):
                # Hanya trigger bila campaign masih aktif; paused tetap menunggu resume manual
                if campaign.status in ("queued", "sending"):
                    dispatch_campaign.delay(str(cid))
                    triggered += 1
        log.info("retry_due: %s penerima dikembalikan ke pending, %s campaign di-trigger",
                 len(due), triggered)
        return {"retried": len(due), "triggered": triggered}
    finally:
        db.close()
