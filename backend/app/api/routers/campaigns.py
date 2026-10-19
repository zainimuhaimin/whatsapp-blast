"""
Campaigns: wizard (create -> ai-extract -> mappings -> recipients -> review ->
confirm) + eksekusi (pause/resume/cancel) + monitoring (stats/messages).
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.models import (
    Campaign,
    CampaignRecipient,
    CampaignVariableMapping,
    Contact,
    TemplateVersion,
    TestNumber,
    User,
)
from app.schemas import (
    AIExtractRequest,
    AIExtractResponse,
    CampaignCreate,
    CampaignOut,
    CampaignUpdate,
    MappingOut,
    MappingsUpdate,
    PageMeta,
    RecipientOut,
    RecipientsBuildRequest,
    RecipientsBuildResponse,
    ReviewOut,
    StatsOut,
)
from app.services import campaign_service, gemini_service
from app.services.audit_service import write_audit

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

EDITABLE_STATUSES = {"draft", "review"}
ACTIVE_SEND_STATUSES = {"queued", "sending"}


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _now():
    return datetime.now(timezone.utc)


def _get_campaign_or_404(db: Session, campaign_id: UUID) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="campaign tidak ditemukan")
    return campaign


def _require_editable(campaign: Campaign):
    if campaign.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"campaign status '{campaign.status}' sudah tidak bisa diubah",
        )


def _recipient_out(db: Session, r: CampaignRecipient) -> RecipientOut:
    out = RecipientOut.model_validate(r)
    if r.contact_id:
        contact = db.get(Contact, r.contact_id)
        out.contact_name = contact.name if contact else None
    return out


@router.get("")
def list_campaigns(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Campaign)
    if status:
        q = q.filter(Campaign.status == status)
    total = q.count()
    items = (
        q.order_by(Campaign.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    pages = (total + limit - 1) // limit if total else 0
    out_items = []
    for c in items:
        d = CampaignOut.model_validate(c).model_dump()
        d["recipient_count"] = campaign_service.recipient_count(db, c.id)
        out_items.append(d)
    return {
        "items": out_items,
        "meta": PageMeta(page=page, limit=limit, total=total, pages=pages),
    }


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(payload: CampaignCreate, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    version = db.get(TemplateVersion, payload.template_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="template version tidak ditemukan")
    send_at = payload.send_at
    if send_at and send_at.tzinfo is None:
        send_at = send_at.replace(tzinfo=timezone.utc)
    campaign = Campaign(
        name=payload.name,
        template_version_id=payload.template_version_id,
        provider=payload.provider,
        is_test_mode=payload.is_test_mode,
        send_at=send_at,
        status="draft",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    write_audit(db, "campaign.create", user_id=user.id, entity_type="campaign",
                entity_id=str(campaign.id),
                metadata={"name": campaign.name, "provider": campaign.provider,
                          "is_test_mode": campaign.is_test_mode},
                ip_address=_ip(request))
    return campaign


@router.get("/{campaign_id}")
def get_campaign(campaign_id: UUID, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    campaign = _get_campaign_or_404(db, campaign_id)
    out = CampaignOut.model_validate(campaign).model_dump()
    out["recipient_count"] = campaign_service.recipient_count(db, campaign.id)
    out["mappings"] = [MappingOut.model_validate(m).model_dump()
                       for m in campaign.variable_mappings]
    version = campaign.template_version
    out["template_version"] = {
        "id": str(version.id),
        "version_number": version.version_number,
        "variables": version.variables,
        "approval_status": version.approval_status,
        "provider_category": version.provider_category,
    }
    return out


@router.put("/{campaign_id}", response_model=CampaignOut)
def update_campaign(campaign_id: UUID, payload: CampaignUpdate, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    campaign = _get_campaign_or_404(db, campaign_id)
    _require_editable(campaign)
    if payload.name is not None:
        campaign.name = payload.name
    if payload.template_version_id is not None and payload.template_version_id != campaign.template_version_id:
        # Ganti template pada draft: pastikan versi ada, lalu reset mapping & penerima
        # karena keduanya terikat pada variabel template lama.
        version = db.get(TemplateVersion, payload.template_version_id)
        if version is None:
            raise HTTPException(status_code=404, detail="template version tidak ditemukan")
        campaign.template_version_id = payload.template_version_id
        db.query(CampaignVariableMapping).filter(
            CampaignVariableMapping.campaign_id == campaign.id).delete(synchronize_session=False)
        db.query(CampaignRecipient).filter(
            CampaignRecipient.campaign_id == campaign.id).delete(synchronize_session=False)
    if payload.send_at is not None:
        send_at = payload.send_at
        if send_at.tzinfo is None:
            send_at = send_at.replace(tzinfo=timezone.utc)
        campaign.send_at = send_at
    if payload.is_test_mode is not None:
        campaign.is_test_mode = payload.is_test_mode
    if payload.provider is not None:
        campaign.provider = payload.provider
    db.commit()
    db.refresh(campaign)
    write_audit(db, "campaign.update", user_id=user.id, entity_type="campaign",
                entity_id=str(campaign.id), metadata={"name": campaign.name},
                ip_address=_ip(request))
    return campaign


@router.delete("/{campaign_id}")
def delete_campaign(campaign_id: UUID, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    campaign = _get_campaign_or_404(db, campaign_id)
    if campaign.status != "draft":
        raise HTTPException(status_code=409,
                            detail="hanya campaign berstatus draft yang bisa dihapus")
    db.delete(campaign)
    db.commit()
    write_audit(db, "campaign.delete", user_id=user.id, entity_type="campaign",
                entity_id=str(campaign.id), metadata={"name": campaign.name},
                ip_address=_ip(request))
    return {"ok": True}


@router.post("/{campaign_id}/ai-extract", response_model=AIExtractResponse)
def ai_extract(campaign_id: UUID, payload: AIExtractRequest, request: Request,
               db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """
    Kirim teks bebas user ke Gemini -> kandidat {variabel: value}.
    Hasil disimpan sebagai mapping sumber 'campaign' (bisa diedit manual
    via PUT mappings sebelum review).
    """
    campaign = _get_campaign_or_404(db, campaign_id)
    _require_editable(campaign)
    variables = campaign.template_version.variables
    values, ai_available = gemini_service.extract_variable_values(payload.input_text, variables)

    saved: dict[str, str] = {}
    for var, value in values.items():
        if var not in variables:
            continue
        existing = (
            db.query(CampaignVariableMapping)
            .filter(CampaignVariableMapping.campaign_id == campaign.id,
                    CampaignVariableMapping.variable_name == var)
            .first()
        )
        if existing:
            existing.source = "campaign"
            existing.contact_field = None
            existing.value = value
        else:
            db.add(CampaignVariableMapping(
                campaign_id=campaign.id, variable_name=var,
                source="campaign", value=value))
        saved[var] = value
    db.commit()
    write_audit(db, "campaign.ai_extract", user_id=user.id, entity_type="campaign",
                entity_id=str(campaign.id),
                metadata={"ai_available": ai_available, "values": saved},
                ip_address=_ip(request))
    return AIExtractResponse(values=saved, ai_available=ai_available)


@router.get("/{campaign_id}/mappings", response_model=list[MappingOut])
def get_mappings(campaign_id: UUID, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    campaign = _get_campaign_or_404(db, campaign_id)
    return list(campaign.variable_mappings)


@router.put("/{campaign_id}/mappings", response_model=list[MappingOut])
def put_mappings(campaign_id: UUID, payload: MappingsUpdate, request: Request,
                 db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """Simpan mapping hasil edit manual user (wajib sebelum review)."""
    campaign = _get_campaign_or_404(db, campaign_id)
    _require_editable(campaign)
    allowed_vars = set(campaign.template_version.variables)
    for item in payload.mappings:
        if item.variable_name not in allowed_vars:
            raise HTTPException(
                status_code=422,
                detail=f"variabel '{item.variable_name}' tidak ada di template",
            )
        if item.source == "contact" and not item.contact_field:
            raise HTTPException(
                status_code=422,
                detail=f"variabel '{item.variable_name}': contact_field wajib diisi",
            )
    for item in payload.mappings:
        existing = (
            db.query(CampaignVariableMapping)
            .filter(CampaignVariableMapping.campaign_id == campaign.id,
                    CampaignVariableMapping.variable_name == item.variable_name)
            .first()
        )
        if existing:
            existing.source = item.source
            existing.contact_field = item.contact_field if item.source == "contact" else None
            existing.value = item.value if item.source == "campaign" else None
        else:
            db.add(CampaignVariableMapping(
                campaign_id=campaign.id,
                variable_name=item.variable_name,
                source=item.source,
                contact_field=item.contact_field if item.source == "contact" else None,
                value=item.value if item.source == "campaign" else None,
            ))
    db.commit()
    write_audit(db, "campaign.mappings_update", user_id=user.id, entity_type="campaign",
                entity_id=str(campaign.id),
                metadata={"mappings": [m.model_dump() for m in payload.mappings]},
                ip_address=_ip(request))
    db.refresh(campaign)
    return list(campaign.variable_mappings)


@router.post("/{campaign_id}/recipients", response_model=RecipientsBuildResponse)
def build_recipients(campaign_id: UUID, payload: RecipientsBuildRequest,
                     request: Request,
                     db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """
    Bangun campaign_recipients. Mode test -> pakai test_numbers aktif
    (contact_ids diabaikan). Blacklist & duplikat nomor otomatis dilewati.
    """
    campaign = _get_campaign_or_404(db, campaign_id)
    _require_editable(campaign)

    existing_phones = {
        row[0]
        for row in db.query(CampaignRecipient.phone)
        .filter(CampaignRecipient.campaign_id == campaign.id)
        .all()
    }

    added = skipped_blacklisted = skipped_duplicate = 0

    def _add(phone: str, contact_id: UUID | None):
        nonlocal added, skipped_duplicate
        if phone in existing_phones:
            skipped_duplicate += 1
            return
        db.add(CampaignRecipient(campaign_id=campaign.id, contact_id=contact_id,
                                phone=phone, status="pending"))
        existing_phones.add(phone)
        added += 1

    if campaign.is_test_mode:
        numbers = db.query(TestNumber).filter(TestNumber.is_active == True).all()
        for tn in numbers:
            _add(tn.phone, None)
    else:
        for cid in payload.contact_ids:
            contact = db.get(Contact, cid)
            if not contact:
                continue
            if contact.is_blacklisted:
                skipped_blacklisted += 1
                continue
            _add(contact.phone, contact.id)
    db.commit()
    total = campaign_service.recipient_count(db, campaign.id)
    write_audit(db, "campaign.recipients_build", user_id=user.id, entity_type="campaign",
                entity_id=str(campaign.id),
                metadata={"added": added, "skipped_blacklisted": skipped_blacklisted,
                          "skipped_duplicate": skipped_duplicate, "total": total,
                          "is_test_mode": campaign.is_test_mode},
                ip_address=_ip(request))
    return RecipientsBuildResponse(added=added,
                                   skipped_blacklisted=skipped_blacklisted,
                                   skipped_duplicate=skipped_duplicate,
                                   total=total)


@router.get("/{campaign_id}/recipients")
def list_recipients(
    campaign_id: UUID,
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_campaign_or_404(db, campaign_id)
    q = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == campaign_id)
    if status:
        q = q.filter(CampaignRecipient.status == status)
    total = q.count()
    items = (
        q.order_by(CampaignRecipient.created_at)
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    pages = (total + limit - 1) // limit if total else 0
    return {
        "items": [_recipient_out(db, r) for r in items],
        "meta": PageMeta(page=page, limit=limit, total=total, pages=pages),
    }


@router.get("/{campaign_id}/review", response_model=ReviewOut)
def review_campaign(campaign_id: UUID, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    campaign = _get_campaign_or_404(db, campaign_id)
    return campaign_service.build_review(db, campaign)


@router.post("/{campaign_id}/confirm")
def confirm_campaign(campaign_id: UUID, request: Request,
                     db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    """
    Validasi penuh -> status 'queued' (atau 'scheduled' bila send_at di masa
    depan) -> enqueue dispatch. Kembalikan daftar error bila validasi gagal.
    """
    campaign = _get_campaign_or_404(db, campaign_id)
    _require_editable(campaign)
    errors = campaign_service.validate_confirm(db, campaign)
    if errors:
        raise HTTPException(status_code=422, detail={"validation_errors": errors})

    now = _now()
    if campaign.send_at and campaign.send_at > now:
        campaign.status = "scheduled"
    else:
        campaign.status = "queued"
    db.commit()

    if campaign.status == "queued":
        from app.worker.tasks.sender import dispatch_campaign

        dispatch_campaign.delay(str(campaign.id))

    write_audit(db, "campaign.confirm_blast", user_id=user.id, entity_type="campaign",
                entity_id=str(campaign.id),
                metadata={"status": campaign.status,
                          "recipients": campaign_service.recipient_count(db, campaign.id),
                          "provider": campaign.provider,
                          "is_test_mode": campaign.is_test_mode},
                ip_address=_ip(request))
    return {"ok": True, "status": campaign.status}


@router.post("/{campaign_id}/pause")
def pause_campaign(campaign_id: UUID, request: Request,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    campaign = _get_campaign_or_404(db, campaign_id)
    if campaign.status not in ACTIVE_SEND_STATUSES and campaign.status != "scheduled":
        raise HTTPException(status_code=409,
                            detail=f"campaign status '{campaign.status}' tidak bisa di-pause")
    campaign.status = "paused"
    db.commit()
    write_audit(db, "campaign.pause", user_id=user.id, entity_type="campaign",
                entity_id=str(campaign.id), ip_address=_ip(request))
    return {"ok": True, "status": campaign.status}


@router.post("/{campaign_id}/resume")
def resume_campaign(campaign_id: UUID, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    campaign = _get_campaign_or_404(db, campaign_id)
    if campaign.status != "paused":
        raise HTTPException(status_code=409,
                            detail="hanya campaign berstatus paused yang bisa di-resume")
    campaign.status = "queued"
    db.commit()
    from app.worker.tasks.sender import dispatch_campaign

    dispatch_campaign.delay(str(campaign.id))
    write_audit(db, "campaign.resume", user_id=user.id, entity_type="campaign",
                entity_id=str(campaign.id), ip_address=_ip(request))
    return {"ok": True, "status": campaign.status}


@router.post("/{campaign_id}/cancel")
def cancel_campaign(campaign_id: UUID, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    campaign = _get_campaign_or_404(db, campaign_id)
    if campaign.status in ("completed", "cancelled"):
        raise HTTPException(status_code=409,
                            detail=f"campaign status '{campaign.status}' tidak bisa di-cancel")
    campaign.status = "cancelled"
    campaign.finished_at = _now()
    db.commit()
    write_audit(db, "campaign.cancel", user_id=user.id, entity_type="campaign",
                entity_id=str(campaign.id), ip_address=_ip(request))
    return {"ok": True, "status": campaign.status}


@router.get("/{campaign_id}/stats", response_model=StatsOut)
def campaign_stats(campaign_id: UUID, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    _get_campaign_or_404(db, campaign_id)
    rows = (
        db.query(CampaignRecipient.status, func.count(CampaignRecipient.id))
        .filter(CampaignRecipient.campaign_id == campaign_id)
        .group_by(CampaignRecipient.status)
        .all()
    )
    counts = {s: c for s, c in rows}
    total = sum(counts.values())
    return StatsOut(
        campaign_id=campaign_id,
        pending=counts.get("pending", 0),
        sent=counts.get("sent", 0),
        delivered=counts.get("delivered", 0),
        read=counts.get("read", 0),
        failed=counts.get("failed", 0),
        total=total,
    )


@router.get("/{campaign_id}/messages")
def campaign_messages(
    campaign_id: UUID,
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Rincian per penerima untuk tabel monitoring."""
    campaign = _get_campaign_or_404(db, campaign_id)
    q = db.query(CampaignRecipient).filter(CampaignRecipient.campaign_id == campaign_id)
    if status:
        q = q.filter(CampaignRecipient.status == status)
    total = q.count()
    items = (
        q.order_by(CampaignRecipient.created_at)
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    pages = (total + limit - 1) // limit if total else 0
    rows = []
    for r in items:
        d = _recipient_out(db, r).model_dump()
        d["rendered_message"] = campaign_service.render_for_recipient(db, campaign, r)
        rows.append(d)
    return {
        "items": rows,
        "meta": PageMeta(page=page, limit=limit, total=total, pages=pages),
    }
