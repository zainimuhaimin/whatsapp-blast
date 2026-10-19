"""Keamanan: hashing password bcrypt + JWT access/refresh token."""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash password dengan bcrypt."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifikasi password terhadap hash bcrypt."""
    return pwd_context.verify(password, password_hash)


def _create_token(subject: str, token_type: str, expires: timedelta) -> tuple[str, str, datetime]:
    """Buat JWT; kembalikan (token, jti, waktu kedaluwarsa)."""
    jti = uuid.uuid4().hex
    exp = datetime.now(timezone.utc) + expires
    payload = {"sub": subject, "type": token_type, "jti": jti, "exp": exp}
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, jti, exp


def create_access_token(subject: str) -> tuple[str, str, datetime]:
    """Access token: 60 menit."""
    return _create_token(subject, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(subject: str) -> tuple[str, str, datetime]:
    """Refresh token: 7 hari."""
    return _create_token(subject, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token: str) -> dict:
    """Decode + validasi signature/exp JWT. Raise jwt.PyJWTError bila tidak valid."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
