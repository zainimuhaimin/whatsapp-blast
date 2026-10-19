"""
Templates: CRUD keluarga template + versioning immutable.
PUT hanya boleh mengubah name/description (bukan body).
DELETE ditolak bila sudah dipakai campaign.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import Campaign, Template, TemplateVersion, User
from app.schemas import (
    TemplateCreate,
    TemplateOut,
    TemplateUpdate,
    TemplateVersionOut,
    VersionApprovalUpdate,
    VersionCreate,
)
from app.services import renderer
from app.services.audit_service import write_audit

router = APIRouter(prefix="/templates", tags=["templates"])

APPROVAL_STATUSES = {"draft", "submitted", "approved", "rejected"}
PROVIDER_CATEGORIES = {"marketing", "utility", "authentication", "service"}


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _get_template_or_404(db: Session, template_id: UUID) -> Template:
    template = db.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="template tidak ditemukan")
    return template


def _latest_version(db: Session, template_id: UUID) -> TemplateVersion | None:
    return (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == template_id)
        .order_by(TemplateVersion.version_number.desc())
        .first()
    )


def _validate_approval_fields(payload) -> None:
    if payload.approval_status and payload.approval_status not in APPROVAL_STATUSES:
        raise HTTPException(status_code=422,
                            detail=f"approval_status harus salah satu dari {sorted(APPROVAL_STATUSES)}")
    if payload.provider_category and payload.provider_category not in PROVIDER_CATEGORIES:
        raise HTTPException(status_code=422,
                            detail=f"provider_category harus salah satu dari {sorted(PROVIDER_CATEGORIES)}")


@router.get("")
def list_templates(db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    templates = db.query(Template).order_by(Template.created_at.desc()).all()
    items = []
    for t in templates:
        out = TemplateOut.model_validate(t)
        latest = _latest_version(db, t.id)
        out.latest_version = TemplateVersionOut.model_validate(latest) if latest else None
        items.append(out)
    return {"items": items}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_template(payload: TemplateCreate, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    if db.query(Template).filter(Template.name == payload.name).first():
        raise HTTPException(status_code=409, detail="nama template sudah dipakai")
    template = Template(name=payload.name, description=payload.description)
    db.add(template)
    db.flush()
    version = TemplateVersion(
        template_id=template.id,
        version_number=1,
        body=payload.body,
        variables=renderer.extract_variables(payload.body),
    )
    db.add(version)
    db.commit()
    write_audit(db, "template.create", user_id=user.id, entity_type="template",
                entity_id=str(template.id),
                metadata={"name": template.name, "variables": version.variables},
                ip_address=_ip(request))
    out = TemplateOut.model_validate(template)
    out.latest_version = TemplateVersionOut.model_validate(version)
    return out


@router.get("/{template_id}")
def get_template(template_id: UUID, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    template = _get_template_or_404(db, template_id)
    out = TemplateOut.model_validate(template)
    latest = _latest_version(db, template.id)
    out.latest_version = TemplateVersionOut.model_validate(latest) if latest else None
    return out


@router.put("/{template_id}", response_model=TemplateOut)
def update_template(template_id: UUID, payload: TemplateUpdate, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    template = _get_template_or_404(db, template_id)
    if payload.name and payload.name != template.name:
        if db.query(Template).filter(Template.name == payload.name,
                                     Template.id != template.id).first():
            raise HTTPException(status_code=409, detail="nama template sudah dipakai")
        template.name = payload.name
    if payload.description is not None:
        template.description = payload.description
    db.commit()
    db.refresh(template)
    write_audit(db, "template.update", user_id=user.id, entity_type="template",
                entity_id=str(template.id),
                metadata={"name": template.name}, ip_address=_ip(request))
    return template


@router.delete("/{template_id}")
def delete_template(template_id: UUID, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    template = _get_template_or_404(db, template_id)
    used = (
        db.query(func.count(Campaign.id))
        .join(TemplateVersion, Campaign.template_version_id == TemplateVersion.id)
        .filter(TemplateVersion.template_id == template.id)
        .scalar()
    )
    if used:
        raise HTTPException(status_code=409,
                            detail=f"template dipakai di {used} campaign dan tidak bisa dihapus")
    db.delete(template)
    db.commit()
    write_audit(db, "template.delete", user_id=user.id, entity_type="template",
                entity_id=str(template.id),
                metadata={"name": template.name}, ip_address=_ip(request))
    return {"ok": True}


@router.get("/{template_id}/versions", response_model=list[TemplateVersionOut])
def list_versions(template_id: UUID, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    _get_template_or_404(db, template_id)
    return (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == template_id)
        .order_by(TemplateVersion.version_number)
        .all()
    )


@router.post("/{template_id}/versions", response_model=TemplateVersionOut,
             status_code=status.HTTP_201_CREATED)
def create_version(template_id: UUID, payload: VersionCreate, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    _get_template_or_404(db, template_id)
    _validate_approval_fields(payload)
    latest = _latest_version(db, template_id)
    next_number = (latest.version_number + 1) if latest else 1
    version = TemplateVersion(
        template_id=template_id,
        version_number=next_number,
        body=payload.body,
        variables=renderer.extract_variables(payload.body),
        provider_template_name=payload.provider_template_name,
        provider_category=payload.provider_category,
        approval_status=payload.approval_status or "draft",
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    write_audit(db, "template.version_create", user_id=user.id, entity_type="template",
                entity_id=str(template_id),
                metadata={"version": next_number, "variables": version.variables},
                ip_address=_ip(request))
    return version


@router.get("/{template_id}/versions/{version_number}", response_model=TemplateVersionOut)
def get_version(template_id: UUID, version_number: int,
                db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    version = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == template_id,
                TemplateVersion.version_number == version_number)
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="versi template tidak ditemukan")
    return version


@router.patch("/{template_id}/versions/{version_number}", response_model=TemplateVersionOut)
def update_version_approval(template_id: UUID, version_number: int,
                            payload: VersionApprovalUpdate, request: Request,
                            db: Session = Depends(get_db),
                            user: User = Depends(get_current_user)):
    """
    Update metadata approval Meta (bukan body — body immutable).
    Dipakai setelah template disubmit/di-approve di WhatsApp Manager.
    """
    version = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == template_id,
                TemplateVersion.version_number == version_number)
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="versi template tidak ditemukan")
    _validate_approval_fields(payload)
    if payload.provider_template_name is not None:
        version.provider_template_name = payload.provider_template_name
    if payload.provider_category is not None:
        version.provider_category = payload.provider_category
    if payload.approval_status is not None:
        version.approval_status = payload.approval_status
    db.commit()
    db.refresh(version)
    write_audit(db, "template.version_approval", user_id=user.id, entity_type="template",
                entity_id=str(template_id),
                metadata={"version": version_number,
                          "approval_status": version.approval_status,
                          "provider_category": version.provider_category},
                ip_address=_ip(request))
    return version
