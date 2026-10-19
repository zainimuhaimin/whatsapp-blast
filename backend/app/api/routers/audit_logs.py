"""Audit logs: list + filter action / rentang tanggal."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import AuditLog, User
from app.schemas import AuditLogOut, PageMeta

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("")
def list_audit_logs(
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None, alias="to"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(AuditLog).options(joinedload(AuditLog.user))
    if action:
        q = q.filter(AuditLog.action == action)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if from_:
        q = q.filter(AuditLog.created_at >= from_)
    if to:
        q = q.filter(AuditLog.created_at <= to)
    total = q.count()
    items = (
        q.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    pages = (total + limit - 1) // limit if total else 0
    out = []
    for entry in items:
        # Dibangun eksplisit (bukan from_attributes) karena atribut Python
        # untuk kolom 'metadata' bernama 'meta' (lihat models).
        out.append(AuditLogOut(
            id=entry.id,
            user_id=entry.user_id,
            username=entry.user.username if entry.user else None,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            metadata=entry.meta,
            ip_address=str(entry.ip_address) if entry.ip_address else None,
            created_at=entry.created_at,
        ).model_dump())
    return {
        "items": out,
        "meta": PageMeta(page=page, limit=limit, total=total, pages=pages),
    }
