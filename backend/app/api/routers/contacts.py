"""
Contacts: CRUD + blacklist toggle.
DELETE ditolak bila kontak sudah dipakai campaign mana pun.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import CampaignRecipient, Contact, User
from app.schemas import (
    BlacklistToggle,
    ContactCreate,
    ContactFindOrCreate,
    ContactFindOrCreateResponse,
    ContactOut,
    ContactUpdate,
    PageMeta,
)
from app.services.audit_service import write_audit

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _get_contact_or_404(db: Session, contact_id: UUID) -> Contact:
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="kontak tidak ditemukan")
    return contact


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("")
def list_contacts(
    search: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    blacklisted: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Contact)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Contact.name.ilike(like), Contact.phone.ilike(like)))
    if tag:
        q = q.filter(Contact.tag == tag)
    if blacklisted is not None:
        q = q.filter(Contact.is_blacklisted == blacklisted)
    total = q.count()
    items = (
        q.order_by(Contact.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    pages = (total + limit - 1) // limit if total else 0
    return {
        "items": [ContactOut.model_validate(c) for c in items],
        "meta": PageMeta(page=page, limit=limit, total=total, pages=pages),
    }


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(payload: ContactCreate, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    if db.query(Contact).filter(Contact.phone == payload.phone).first():
        raise HTTPException(status_code=409, detail="nomor telepon sudah terdaftar")
    contact = Contact(name=payload.name, phone=payload.phone,
                      tag=payload.tag, notes=payload.notes,
                      data=dict(payload.data or {}))
    db.add(contact)
    db.commit()
    db.refresh(contact)
    write_audit(db, "contact.create", user_id=user.id, entity_type="contact",
                entity_id=str(contact.id),
                metadata={"name": contact.name, "phone": contact.phone}, ip_address=_ip(request))
    return contact


@router.post("/find-or-create", response_model=ContactFindOrCreateResponse)
def find_or_create_contact(payload: ContactFindOrCreate, request: Request,
                           db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    """
    Cari kontak berdasar nomor telepon. Nomor otomatis dinormalisasi
    (0812… == +62812… == 62812…), jadi nomor identik beda format tidak
    akan dobel. Bila belum ada -> buat kontak baru otomatis.
    Dipakai untuk input nomor cepat (mis. nomor PIC) di wizard campaign.
    """
    existing = db.query(Contact).filter(Contact.phone == payload.phone).first()
    if existing:
        name = (payload.name or "").strip()
        if name and existing.name == existing.phone:
            # kontak hasil auto-create (nama == nomor) -> perbarui namanya
            existing.name = name
            db.commit()
            db.refresh(existing)
            write_audit(db, "contact.quick_add_name", user_id=user.id,
                        entity_type="contact", entity_id=str(existing.id),
                        metadata={"name": name, "phone": existing.phone},
                        ip_address=_ip(request))
        return {"contact": existing, "created": False}
    name = (payload.name or "").strip() or payload.phone
    contact = Contact(name=name, phone=payload.phone,
                      tag=payload.tag, notes=payload.notes)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    write_audit(db, "contact.quick_add", user_id=user.id, entity_type="contact",
                entity_id=str(contact.id),
                metadata={"name": contact.name, "phone": contact.phone},
                ip_address=_ip(request))
    return {"contact": contact, "created": True}


@router.get("/data-keys")
def contact_data_keys(db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """Daftar key dinamis unik dari data JSONB semua kontak (untuk dropdown
    mapping field kontak di wizard)."""
    from sqlalchemy import func

    rows = db.query(func.distinct(func.jsonb_object_keys(Contact.data))).all()
    keys = sorted({r[0] for r in rows if r[0]})
    return {"keys": keys}


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(contact_id: UUID, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    return _get_contact_or_404(db, contact_id)


@router.put("/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: UUID, payload: ContactUpdate, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    contact = _get_contact_or_404(db, contact_id)
    dup = db.query(Contact).filter(Contact.phone == payload.phone,
                                   Contact.id != contact.id).first()
    if dup:
        raise HTTPException(status_code=409, detail="nomor telepon sudah dipakai kontak lain")
    old = {"name": contact.name, "phone": contact.phone, "tag": contact.tag}
    contact.name, contact.phone, contact.tag, contact.notes = (
        payload.name, payload.phone, payload.tag, payload.notes)
    contact.data = dict(payload.data or {})
    db.commit()
    db.refresh(contact)
    write_audit(db, "contact.update", user_id=user.id, entity_type="contact",
                entity_id=str(contact.id),
                metadata={"old": old, "new": {"name": contact.name,
                                              "phone": contact.phone, "tag": contact.tag}},
                ip_address=_ip(request))
    return contact


@router.delete("/{contact_id}")
def delete_contact(contact_id: UUID, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    contact = _get_contact_or_404(db, contact_id)
    used = (
        db.query(func.count(CampaignRecipient.id))
        .filter(CampaignRecipient.contact_id == contact.id)
        .scalar()
    )
    if used:
        raise HTTPException(
            status_code=409,
            detail=f"kontak dipakai di {used} campaign; pakai blacklist untuk menonaktifkan",
        )
    db.delete(contact)
    db.commit()
    write_audit(db, "contact.delete", user_id=user.id, entity_type="contact",
                entity_id=str(contact.id),
                metadata={"name": contact.name, "phone": contact.phone}, ip_address=_ip(request))
    return {"ok": True}


@router.patch("/{contact_id}/blacklist", response_model=ContactOut)
def toggle_blacklist(contact_id: UUID, payload: BlacklistToggle, request: Request,
                      db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    contact = _get_contact_or_404(db, contact_id)
    old = contact.is_blacklisted
    contact.is_blacklisted = payload.is_blacklisted
    db.commit()
    db.refresh(contact)
    write_audit(db, "contact.blacklist", user_id=user.id, entity_type="contact",
                entity_id=str(contact.id),
                metadata={"old": old, "new": contact.is_blacklisted}, ip_address=_ip(request))
    return contact
