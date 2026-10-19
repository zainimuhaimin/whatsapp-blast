"""Koneksi database (SQLAlchemy) dan Redis."""
from collections.abc import Iterator

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    """Dependency FastAPI: session DB per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Singleton client Redis (dipakai untuk blacklist token & token bucket)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client
