"""
Auth: login / logout / me (+ refresh).
Token disimpan di httpOnly cookie; logout mem-blacklist jti di Redis.
"""
from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db, get_redis
from app.core.deps import ACCESS_COOKIE, get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models import User
from app.schemas import LoginRequest, UserOut
from app.services.audit_service import write_audit

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"


def _set_auth_cookies(response: Response, access: str, refresh: str):
    # httpOnly: JS tidak bisa membaca -> tahan XSS
    response.set_cookie(ACCESS_COOKIE, access, httponly=True, samesite="lax", path="/")
    response.set_cookie(REFRESH_COOKIE, refresh, httponly=True, samesite="lax", path="/api/auth")


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, request: Request, response: Response,
          db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="username atau password salah")
    access, _, _ = create_access_token(str(user.id))
    refresh, _, _ = create_refresh_token(str(user.id))
    _set_auth_cookies(response, access, refresh)
    write_audit(db, "auth.login", user_id=user.id, entity_type="user",
                entity_id=str(user.id),
                metadata={"username": user.username},
                ip_address=request.client.host if request.client else None)
    return user


@router.post("/logout")
def logout(request: Request, response: Response,
           user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    # Blacklist access token sampai kedaluwarsa
    token = request.cookies.get(ACCESS_COOKIE)
    if token:
        try:
            payload = decode_token(token)
            jti, exp = payload.get("jti"), payload.get("exp")
            if jti and exp:
                import time

                ttl = max(1, int(exp - time.time()))
                get_redis().setex(f"bl:{jti}", ttl, "1")
        except jwt.PyJWTError:
            pass
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
    write_audit(db, "auth.logout", user_id=user.id, entity_type="user",
                entity_id=str(user.id),
                ip_address=request.client.host if request.client else None)
    return {"ok": True}


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    """Tukar refresh token -> access token baru (httpOnly cookie)."""
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="refresh token tidak ada")
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="refresh token tidak valid")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="tipe token salah")
    access, _, _ = create_access_token(payload["sub"])
    response.set_cookie(ACCESS_COOKIE, access, httponly=True, samesite="lax", path="/")
    return {"ok": True}


@router.get("/config")
def auth_config():
    """Info publik: apakah login dinonaktifkan (AUTH_DISABLED)."""
    return {"auth_disabled": settings.AUTH_DISABLED}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
