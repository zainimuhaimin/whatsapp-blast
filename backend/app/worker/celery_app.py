"""Celery app: 2 queue (wa_sender concurrency=1, default) + Beat schedule."""
from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from app.core.config import settings

celery_app = Celery(
    "wa_blast",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    # WAJIB: daftarkan modul task agar worker me-register semua task.
    # Tanpa ini, worker tidak mengenal task apa pun -> "Received unregistered task".
    include=[
        "app.worker.tasks.campaigns",
        "app.worker.tasks.sender",
        "app.worker.tasks.webhooks",
        "app.worker.tasks.maintenance",
    ],
)

celery_app.conf.update(
    task_queues=(
        Queue("wa_sender", routing_key="wa_sender"),
        Queue("default", routing_key="default"),
    ),
    task_default_queue="default",
    task_routes={
        "sender.dispatch_campaign": {"queue": "wa_sender"},
    },
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="Asia/Jakarta",
    enable_utc=True,
    beat_schedule={
        "campaigns.enqueue_due": {
            "task": "campaigns.enqueue_due",
            "schedule": 60.0,  # tiap 1 menit
        },
        "campaigns.retry_due": {
            "task": "campaigns.retry_due",
            "schedule": 300.0,  # tiap 5 menit
        },
        "maintenance.cleanup_tokens": {
            "task": "maintenance.cleanup_tokens",
            "schedule": crontab(hour=3, minute=0),  # harian
        },
    },
)
