"""
Task maintenance: maintenance.cleanup_tokens (Beat harian).

Blacklist token logout disimpan di Redis dengan TTL = sisa umur token,
jadi kedaluwarsa otomatis. Task ini housekeeping defensif: membersihkan
sisa kunci blacklist yang TTL-nya hilang/tidak valid.
"""
import logging

from app.core.db import get_redis
from app.worker.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="maintenance.cleanup_tokens")
def cleanup_tokens():
    r = get_redis()
    cleaned = 0
    for key in r.scan_iter("bl:*", count=500):
        ttl = r.ttl(key)
        if ttl == -1:  # tanpa TTL -> hapus agar tidak menumpuk selamanya
            r.delete(key)
            cleaned += 1
    log.info("cleanup_tokens: %s kunci blacklist tanpa TTL dibersihkan", cleaned)
    return {"cleaned": cleaned}
