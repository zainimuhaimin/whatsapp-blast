"""Test numbers: nomor sandbox untuk mode test campaign."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import TestNumber, User
from app.schemas import TestNumberCreate, TestNumberOut, TestNumberUpdate
from app.services.audit_service import write_audit

router = APIRouter(prefix="/test-numbers", tags=["test-numbers"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _get_or_404(db: Session, number_id: UUID) -> TestNumber:
    tn = db.get(TestNumber, number_id)
    if not tn:
        raise HTTPException(status_code=404, detail="nomor test tidak ditemukan")
    return tn


@router.get("", response_model=list[TestNumberOut])
def list_test_numbers(db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    return db.query(TestNumber).order_by(TestNumber.created_at).all()


@router.post("", response_model=TestNumberOut, status_code=status.HTTP_201_CREATED)
def create_test_number(payload: TestNumberCreate, request: Request,
                       db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    if db.query(TestNumber).filter(TestNumber.phone == payload.phone).first():
        raise HTTPException(status_code=409, detail="nomor sudah terdaftar")
    tn = TestNumber(label=payload.label, phone=payload.phone)
    db.add(tn)
    db.commit()
    db.refresh(tn)
    write_audit(db, "test_number.create", user_id=user.id, entity_type="test_number",
                entity_id=str(tn.id),
                metadata={"label": tn.label, "phone": tn.phone}, ip_address=_ip(request))
    return tn


@router.put("/{number_id}", response_model=TestNumberOut)
def update_test_number(number_id: UUID, payload: TestNumberUpdate, request: Request,
                       db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    tn = _get_or_404(db, number_id)
    old = {"label": tn.label, "phone": tn.phone, "is_active": tn.is_active}
    if payload.label is not None:
        tn.label = payload.label
    if payload.phone is not None:
        dup = db.query(TestNumber).filter(TestNumber.phone == payload.phone,
                                          TestNumber.id != tn.id).first()
        if dup:
            raise HTTPException(status_code=409, detail="nomor sudah dipakai nomor lain")
        tn.phone = payload.phone
    if payload.is_active is not None:
        tn.is_active = payload.is_active
    db.commit()
    db.refresh(tn)
    write_audit(db, "test_number.update", user_id=user.id, entity_type="test_number",
                entity_id=str(tn.id),
                metadata={"old": old,
                          "new": {"label": tn.label, "phone": tn.phone,
                                  "is_active": tn.is_active}},
                ip_address=_ip(request))
    return tn


@router.delete("/{number_id}")
def delete_test_number(number_id: UUID, request: Request,
                       db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    tn = _get_or_404(db, number_id)
    db.delete(tn)
    db.commit()
    write_audit(db, "test_number.delete", user_id=user.id, entity_type="test_number",
                entity_id=str(tn.id),
                metadata={"label": tn.label, "phone": tn.phone}, ip_address=_ip(request))
    return {"ok": True}
