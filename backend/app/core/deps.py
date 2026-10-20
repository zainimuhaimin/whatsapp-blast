"""Dependency auth: user aktif dari cookie httpOnly / header Bearer."""
import uuid

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db, get_redis
from app.core.security import decode_token
from app.models import User

ACCESS_COOKIE = "access_token"


def _extract_token_or_none(
    access_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> str | None:
    if access_token:
        return access_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _auto_login_user(db: Session) -> User:
    """User untuk mode AUTH_DISABLED: user aktif pertama; bila belum ada
    user sama sekali, buat admin default dari konfigurasi."""
    user = (
        db.query(User)
        .filter(User.is_active == True)  # noqa: E712
        .order_by(User.created_at)
        .first()
    )
    if user:
        return user
    from app.core.security import hash_password

    user = User(
        username=settings.ADMIN_USERNAME,
        password_hash=hash_password(settings.ADMIN_PASSWORD),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    token: str | None = Depends(_extract_token_or_none),
    db: Session = Depends(get_db),
) -> User:
    """Validasi JWT, cek blacklist Redis, kembalikan user aktif.
    Bila AUTH_DISABLED aktif, lewati validasi token & auto-login."""
    if settings.AUTH_DISABLED:
        return _auto_login_user(db)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="belum login"
        )
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="token tidak valid"
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="tipe token salah"
        )
    jti = payload.get("jti")
    if get_redis().exists(f"bl:{jti}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="token sudah logout"
        )
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="token tidak valid"
        )
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="akun tidak aktif"
        )
    return user
