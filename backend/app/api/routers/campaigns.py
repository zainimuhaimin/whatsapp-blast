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
from app.core.phone import normalize_phone
from app.models import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientVariable,
    CampaignVariableMapping,
    Contact,
    TemplateVersion,
    TestNumber,
    User,
)
from app.schemas import (
    AIApplyRecipientsRequest,
    AIApplyRecipientsResponse,
    AIExtractRequest,
    AIExtractResponse,
    AIParseRecipientsRequest,
    AIParseRecipientsResponse,
    AIParsedRecipient,
    CampaignCreate,
    CampaignOut,
    CampaignUpdate,
    MappingOut,
    MappingsUpdate,
    PageMeta,
    RecipientOut,
    RecipientVariableItem,
    RecipientVariablesUpdate,
    RecipientVariablesResponse,
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


@router.post("/{campaign_id}/recipients/{recipient_id}/retry")
def retry_recipient(campaign_id: UUID, recipient_id: UUID, request: Request,
                    db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    """
    Coba ulang kirim ke satu penerima yang gagal (tombol retry per penerima).
    Reset ke 'pending'; bila campaign sudah 'completed', kembalikan ke 'queued'
    dan trigger dispatch agar worker memprosesnya.
    """
    campaign = _get_campaign_or_404(db, campaign_id)
    recipient = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.id == recipient_id,
                CampaignRecipient.campaign_id == campaign.id)
        .first()
    )
    if not recipient:
        raise HTTPException(status_code=404, detail="penerima tidak ditemukan")
    if recipient.status != "failed":
        raise HTTPException(
            status_code=409,
            detail=f"hanya penerima berstatus 'failed' yang bisa di-retry "
                   f"(saat ini: '{recipient.status}')",
        )
    if campaign.status == "cancelled":
        raise HTTPException(status_code=409, detail="campaign sudah dibatalkan")
    if campaign.provider == "manual":
        raise HTTPException(
            status_code=409,
            detail="campaign jalur manual tidak memakai retry otomatis — "
                   "kirim ulang via tombol WhatsApp di halaman detail",
        )

    recipient.status = "pending"
    recipient.retry_count = 0
    recipient.last_error = None
    recipient.next_retry_at = None
    requeued = False
    if campaign.status == "completed":
        campaign.status = "queued"
        campaign.finished_at = None
        requeued = True
    db.commit()

    if campaign.status in ("queued", "sending"):
        from app.worker.tasks.sender import dispatch_campaign
        dispatch_campaign.delay(str(campaign.id))

    write_audit(db, "campaign.recipient_retry", user_id=user.id,
                entity_type="campaign", entity_id=str(campaign.id),
                metadata={"recipient_id": str(recipient.id),
                          "phone": recipient.phone, "requeued": requeued},
                ip_address=_ip(request))
    return {"ok": True, "recipient_id": str(recipient.id),
            "status": "pending", "requeued": requeued}


@router.post("/{campaign_id}/recipients/{recipient_id}/manual-status")
def manual_recipient_status(campaign_id: UUID, recipient_id: UUID,
                            payload: dict, request: Request,
                            db: Session = Depends(get_db),
                            user: User = Depends(get_current_user)):
    """
    Tandai hasil pengiriman manual (wa.me) untuk audit:
    status 'sent' (terkirim manual) atau 'skipped' (dilewatkan).
    Tidak me-trigger dispatch otomatis.
    """
    campaign = _get_campaign_or_404(db, campaign_id)
    recipient = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.id == recipient_id,
                CampaignRecipient.campaign_id == campaign.id)
        .first()
    )
    if not recipient:
        raise HTTPException(status_code=404, detail="penerima tidak ditemukan")
    new_status = (payload.get("status") or "").strip().lower()
    if new_status not in ("sent", "skipped"):
        raise HTTPException(
            status_code=400,
            detail="status harus 'sent' (terkirim) atau 'skipped' (dilewatkan)",
        )
    if campaign.status == "cancelled":
        raise HTTPException(status_code=409, detail="campaign sudah dibatalkan")
    if recipient.status in ("sent", "delivered", "read"):
        raise HTTPException(
            status_code=409,
            detail=f"penerima sudah berstatus '{recipient.status}', tidak perlu ditandai lagi",
        )

    old_status = recipient.status
    recipient.status = new_status
    recipient.next_retry_at = None
    if new_status == "sent":
        recipient.sent_at = _now()
        recipient.last_error = None
    else:
        recipient.last_error = "dilewatkan secara manual oleh pengguna"
    db.commit()

    # Auto-complete: semua penerima sudah resolved (tidak ada pending)
    if campaign.status == "sending":
        remaining = (
            db.query(CampaignRecipient)
            .filter(CampaignRecipient.campaign_id == campaign.id,
                    CampaignRecipient.status == "pending")
            .count()
        )
        if remaining == 0:
            campaign.status = "completed"
            campaign.finished_at = _now()
            db.commit()

    write_audit(db, "campaign.recipient_manual_status", user_id=user.id,
                entity_type="campaign", entity_id=str(campaign.id),
                metadata={"recipient_id": str(recipient.id),
                          "phone": recipient.phone,
                          "old_status": old_status, "new_status": new_status},
                ip_address=_ip(request))
    return {"ok": True, "recipient_id": str(recipient.id),
            "old_status": old_status, "status": new_status}


@router.post("/{campaign_id}/message-body")
def update_message_body(campaign_id: UUID, payload: dict, request: Request,
                        db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """
    Ubah teks pesan campaign secara fleksibel (mis. setelah input AI):
    membuat versi template BARU (immutable versioning) dan mengarahkan
    campaign ke versi tersebut. Mapping yang sudah ada ikut terbawa
    karena keyed by nama variabel.
    """
    from app.services import renderer

    campaign = _get_campaign_or_404(db, campaign_id)
    _require_editable(campaign)
    body = (payload.get("body") or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="isi pesan tidak boleh kosong")
    if len(body) > 10000:
        raise HTTPException(status_code=400, detail="isi pesan maksimal 10000 karakter")

    variables = renderer.extract_variables(body)
    current = db.get(TemplateVersion, campaign.template_version_id)
    if current and (current.body or "").strip() == body:
        # Tidak ada perubahan — kembalikan versi yang sedang dipakai
        write_audit(db, "campaign.message_body_update", user_id=user.id,
                    entity_type="campaign", entity_id=str(campaign.id),
                    metadata={"template_version_id": str(current.id),
                              "version_number": current.version_number,
                              "variables": current.variables, "unchanged": True},
                    ip_address=_ip(request))
        return {"ok": True,
                "template_version_id": str(current.id),
                "version_number": current.version_number,
                "variables": current.variables,
                "unchanged": True}
    max_vn = (
        db.query(func.max(TemplateVersion.version_number))
        .filter(TemplateVersion.template_id == current.template_id)
        .scalar()
        or 0
    )
    version = TemplateVersion(
        template_id=current.template_id,
        version_number=max_vn + 1,
        body=body,
        variables=variables,
    )
    db.add(version)
    db.flush()
    campaign.template_version_id = version.id
    db.commit()

    write_audit(db, "campaign.message_body_update", user_id=user.id,
                entity_type="campaign", entity_id=str(campaign.id),
                metadata={"template_version_id": str(version.id),
                          "version_number": version.version_number,
                          "variables": variables},
                ip_address=_ip(request))
    return {"ok": True,
            "template_version_id": str(version.id),
            "version_number": version.version_number,
            "variables": variables}


@router.get("/{campaign_id}/chat-links")
def chat_links(campaign_id: UUID,
               page: int = Query(default=1, ge=1),
               limit: int = Query(default=50, ge=1, le=200),
               db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """
    Daftar link wa.me per penerima — kirim manual yang aman (tanpa otomasi).
    Tiap link membuka WhatsApp dengan pesan yang sudah di-render untuk
    penerima tersebut; user tinggal tekan kirim di aplikasi WA.
    """
    from urllib.parse import quote

    campaign = _get_campaign_or_404(db, campaign_id)
    q = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == campaign.id)
        .order_by(CampaignRecipient.created_at)
    )
    total = q.count()
    items = q.offset((page - 1) * limit).limit(limit).all()
    out = []
    for r in items:
        message = campaign_service.render_for_recipient(db, campaign, r)
        # wa.me butuh digit internasional tanpa '+'
        phone_digits = "".join(ch for ch in (r.phone or "") if ch.isdigit())
        wa_url = f"https://wa.me/{phone_digits}?text={quote(message)}" if phone_digits else None
        name = r.contact.name if r.contact_id and r.contact else None
        out.append({
            "recipient_id": str(r.id),
            "phone": r.phone,
            "name": name,
            "status": r.status,
            "message": message,
            "wa_url": wa_url,
        })
    pages = (total + limit - 1) // limit if total else 0
    return {"items": out, "meta": PageMeta(page=page, limit=limit, total=total, pages=pages)}


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
        "body": version.body,
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
    values, ai_available = gemini_service.extract_variable_values(
        payload.input_text, variables,
        template_body=campaign.template_version.body,
        db=db,
    )

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


@router.post("/{campaign_id}/ai-parse-recipients", response_model=AIParseRecipientsResponse)
def ai_parse_recipients(campaign_id: UUID, payload: AIParseRecipientsRequest,
                        request: Request, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """
    Parse teks bebas user -> daftar KANDIDAT penerima (TANPA menyimpan).
    Tiap kandidat: nomor (mentah & ternormalisasi), nama, dan nilai variabel
    khusus baris itu. User memeriksa/mengedit di UI sebelum apply.
    """
    campaign = _get_campaign_or_404(db, campaign_id)
    _require_editable(campaign)
    variables = campaign.template_version.variables
    items, ai_available = gemini_service.extract_recipients(
        payload.input_text, variables,
        template_body=campaign.template_version.body,
        db=db,
    )
    out: list[AIParsedRecipient] = []
    for it in items:
        raw_phone = str(it.get("phone") or "").strip()
        try:
            normalized = normalize_phone(raw_phone) if raw_phone else ""
            valid = bool(normalized)
        except ValueError:
            normalized, valid = "", False
        contact = (
            db.query(Contact).filter(Contact.phone == normalized).first()
            if valid else None
        )
        out.append(AIParsedRecipient(
            phone=raw_phone,
            phone_normalized=normalized,
            phone_valid=valid,
            name=str(it.get("name") or "").strip(),
            variables={k: str(v or "") for k, v in (it.get("variables") or {}).items()},
            contact_exists=contact is not None,
            contact_name=contact.name if contact else None,
        ))
    return AIParseRecipientsResponse(items=out, ai_available=ai_available)


def _apply_recipient_rows(db: Session, campaign: Campaign,
                         rows: list[dict], variables: set[str]):
    """
    Inti penyimpanan daftar penerima (dipakai AI-apply & file-apply):
    find-or-create kontak per nomor, tambah recipient, simpan override
    variabel per penerima. Satu nomor BOLEH masuk berkali-kali — tiap
    baris menjadi satu pesan terkirim. Hanya variabel yang ada di
    `variables` (variabel template) yang disimpan sebagai override.

    rows: [{phone, name, variables{var: value}}]
    Return: (added, created_contacts, matched_contacts, skipped[])
    """
    def _sig(phone_: str, vars_: dict) -> tuple:
        return (phone_, tuple(sorted((k, str(v or "")) for k, v in vars_.items())))

    existing_sigs = set()
    for r in db.query(CampaignRecipient).filter(
            CampaignRecipient.campaign_id == campaign.id).all():
        ov = {rv.variable_name: (rv.value or "") for rv in (r.variable_overrides or [])}
        existing_sigs.add(_sig(r.phone, ov))

    added = created = matched = 0
    skipped: list[str] = []
    for item in rows:
        phone_raw = (item.get("phone") or "").strip()
        try:
            phone = normalize_phone(phone_raw)
        except ValueError:
            skipped.append(f"{phone_raw or '(kosong)'}: nomor tidak valid, dilewati")
            continue
        item_vars = {k: str(v or "") for k, v in (item.get("variables") or {}).items()
                     if k in variables}
        if _sig(phone, item_vars) in existing_sigs:
            skipped.append(f"{phone}: baris identik sudah ada, dilewati")
            continue
        contact = db.query(Contact).filter(Contact.phone == phone).first()
        name = (item.get("name") or "").strip()
        if contact:
            matched += 1
            if name and contact.name == contact.phone:
                contact.name = name  # kontak auto-create -> perbarui namanya
        else:
            created += 1
            contact = Contact(name=name or phone, phone=phone)
            db.add(contact)
            db.flush()
        if contact.is_blacklisted:
            skipped.append(f"{phone}: kontak di-blacklist, dilewati")
            continue
        recipient = CampaignRecipient(
            campaign_id=campaign.id, contact_id=contact.id, phone=phone)
        db.add(recipient)
        db.flush()
        for var, val in item_vars.items():
            db.add(CampaignRecipientVariable(
                recipient_id=recipient.id, variable_name=var, value=val))
        existing_sigs.add(_sig(phone, item_vars))
        added += 1
    return added, created, matched, skipped


@router.post("/{campaign_id}/ai-apply-recipients", response_model=AIApplyRecipientsResponse)
def ai_apply_recipients(campaign_id: UUID, payload: AIApplyRecipientsRequest,
                        request: Request, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    """
    Simpan daftar penerima (hasil parse AI yang sudah diperiksa/diedit user):
    find-or-create kontak per nomor, tambah recipient, simpan override
    variabel per penerima. Satu nomor BOLEH masuk berkali-kali — tiap baris
    menjadi satu pesan terkirim.
    """
    campaign = _get_campaign_or_404(db, campaign_id)
    _require_editable(campaign)
    variables = set(campaign.template_version.variables or [])
    rows = [{"phone": item.phone, "name": item.name,
             "variables": dict(item.variables or {})} for item in payload.items]
    added, created, matched, skipped = _apply_recipient_rows(db, campaign, rows, variables)
    db.commit()
    write_audit(db, "campaign.ai_apply_recipients", user_id=user.id,
                entity_type="campaign", entity_id=str(campaign.id),
                metadata={"added": added, "created_contacts": created,
                          "matched_contacts": matched, "skipped": skipped},
                ip_address=_ip(request))
    return AIApplyRecipientsResponse(
        added=added, created_contacts=created,
        matched_contacts=matched, skipped=skipped)


@router.post("/{campaign_id}/apply-file")
def apply_file(campaign_id: UUID, payload: dict, request: Request,
               db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """
    Terapkan data file (hasil parse /file-uploads) ke campaign yang sudah ada:
    tiap baris menjadi penerima + override variabel per baris.
    Dipakai tab 'Upload file' di wizard langkah 3 (alur unified).
    """
    from app.models import FileUpload

    campaign = _get_campaign_or_404(db, campaign_id)
    _require_editable(campaign)
    try:
        upload_id = UUID(str(payload.get("upload_id") or ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="upload_id tidak valid")
    upload = db.get(FileUpload, upload_id)
    if not upload or (upload.user_id and upload.user_id != user.id):
        raise HTTPException(status_code=404, detail="file upload tidak ditemukan")
    columns = {c["variable"] for c in (upload.columns or []) if c.get("variable")}
    phone_variable = (payload.get("phone_variable") or "").strip()
    if phone_variable not in columns:
        raise HTTPException(
            status_code=400,
            detail="pilih kolom nomor telepon yang valid dari file",
        )
    variables = set(campaign.template_version.variables or [])
    rows = []
    for row in (upload.rows or []):
        name = ""
        for nk in ("nama", "name", "nama_lengkap"):
            if row.get(nk):
                name = str(row[nk])
                break
        vars_ = {k: str(v) for k, v in row.items()
                 if k != phone_variable and v not in (None, "")}
        rows.append({"phone": str(row.get(phone_variable) or ""),
                     "name": name, "variables": vars_})
    added, created, matched, skipped = _apply_recipient_rows(db, campaign, rows, variables)
    db.commit()
    write_audit(db, "campaign.apply_file", user_id=user.id,
                entity_type="campaign", entity_id=str(campaign.id),
                metadata={"upload_id": str(upload.id), "filename": upload.filename,
                          "added": added, "created_contacts": created,
                          "matched_contacts": matched, "skipped": skipped},
                ip_address=_ip(request))
    return {"ok": True, "added": added, "created_contacts": created,
            "matched_contacts": matched, "skipped": skipped}


@router.get("/{campaign_id}/recipient-variables", response_model=RecipientVariablesResponse)
def get_recipient_variables(campaign_id: UUID, db: Session = Depends(get_db),
                            user: User = Depends(get_current_user)):
    """
    Ringkasan nilai variabel per penerima (hasil AI per baris / edit manual):
    dipakai wizard langkah Mapping untuk menampilkan variabel yang sudah
    terisi AI agar tidak perlu di-mapping manual lagi.
    """
    from app.schemas import RecipientVariableEntry, RecipientVariableSummary
    campaign = _get_campaign_or_404(db, campaign_id)
    recipients = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == campaign.id)
        .order_by(CampaignRecipient.created_at)
        .all()
    )
    contact_names = {}
    for r in recipients:
        if r.contact_id and r.contact_id not in contact_names:
            c = db.get(Contact, r.contact_id)
            contact_names[r.contact_id] = c.name if c else ""
    by_var: dict[str, list] = {}
    for r in recipients:
        for rv in (r.variable_overrides or []):
            by_var.setdefault(rv.variable_name, []).append(
                RecipientVariableEntry(
                    recipient_id=str(r.id), phone=r.phone,
                    name=contact_names.get(r.contact_id, ""),
                    value=rv.value or "",
                )
            )
    return RecipientVariablesResponse(
        variables=[
            RecipientVariableSummary(
                variable_name=var, recipient_count=len(entries), entries=entries)
            for var, entries in sorted(by_var.items())
        ],
        total_recipients=len(recipients),
    )


@router.put("/{campaign_id}/recipient-variables", response_model=RecipientVariablesResponse)
def put_recipient_variables(campaign_id: UUID, payload: RecipientVariablesUpdate,
                            request: Request, db: Session = Depends(get_db),
                            user: User = Depends(get_current_user)):
    """Simpan/ubah nilai variabel per penerima (edit manual dari wizard)."""
    campaign = _get_campaign_or_404(db, campaign_id)
    _require_editable(campaign)
    allowed_vars = set(campaign.template_version.variables or [])
    recipient_ids = {str(row[0]) for row in db.query(CampaignRecipient.id).filter(
        CampaignRecipient.campaign_id == campaign.id).all()}
    for item in payload.items:
        if item.variable_name not in allowed_vars:
            raise HTTPException(
                status_code=422,
                detail=f"variabel '{item.variable_name}' tidak ada di template")
        if item.recipient_id not in recipient_ids:
            raise HTTPException(
                status_code=422, detail="recipient tidak termasuk campaign ini")
    for item in payload.items:
        existing = (
            db.query(CampaignRecipientVariable)
            .join(CampaignRecipient,
                  CampaignRecipient.id == CampaignRecipientVariable.recipient_id)
            .filter(CampaignRecipientVariable.recipient_id == item.recipient_id,
                    CampaignRecipientVariable.variable_name == item.variable_name)
            .first()
        )
        if existing:
            existing.value = item.value
        else:
            db.add(CampaignRecipientVariable(
                recipient_id=item.recipient_id,
                variable_name=item.variable_name, value=item.value))
    db.commit()
    write_audit(db, "campaign.recipient_variables_update", user_id=user.id,
                entity_type="campaign", entity_id=str(campaign.id),
                metadata={"updated": len(payload.items)}, ip_address=_ip(request))
    return get_recipient_variables(campaign_id, db, user)


@router.delete("/{campaign_id}/recipient-variables/{variable_name}")
def delete_recipient_variable(campaign_id: UUID, variable_name: str,
                              request: Request, db: Session = Depends(get_db),
                              user: User = Depends(get_current_user)):
    """Hapus semua nilai per-penerima untuk satu variabel (kembali ke mapping manual)."""
    campaign = _get_campaign_or_404(db, campaign_id)
    _require_editable(campaign)
    deleted = (
        db.query(CampaignRecipientVariable)
        .join(CampaignRecipient,
              CampaignRecipient.id == CampaignRecipientVariable.recipient_id)
        .filter(CampaignRecipient.campaign_id == campaign.id,
                CampaignRecipientVariable.variable_name == variable_name)
        .delete(synchronize_session=False)
    )
    db.commit()
    write_audit(db, "campaign.recipient_variable_clear", user_id=user.id,
                entity_type="campaign", entity_id=str(campaign.id),
                metadata={"variable": variable_name, "deleted": deleted},
                ip_address=_ip(request))
    return {"ok": True, "deleted": deleted}


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

    added = skipped_blacklisted = skipped_duplicate = skipped_no_data = 0

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
        # Nomor test yang tidak punya data sama sekali (tidak masuk dari input
        # AI, tidak bisa di-resolve via mapping) tidak dibawa — agar tidak
        # menimbulkan pesan kosong / error saat kirim.
        template_vars = campaign.template_version.variables or []
        prospective = campaign_service._prospective_test_values(db, campaign)
        no_data_at_all = bool(template_vars) and not any(
            (prospective.get(v) or "").strip() for v in template_vars
        )
        for tn in numbers:
            if tn.phone not in existing_phones and no_data_at_all:
                skipped_no_data += 1
                continue
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
                          "skipped_duplicate": skipped_duplicate,
                          "skipped_no_data": skipped_no_data, "total": total,
                          "is_test_mode": campaign.is_test_mode},
                ip_address=_ip(request))
    return RecipientsBuildResponse(added=added,
                                   skipped_blacklisted=skipped_blacklisted,
                                   skipped_duplicate=skipped_duplicate,
                                   skipped_no_data=skipped_no_data,
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
        skipped=counts.get("skipped", 0),
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
