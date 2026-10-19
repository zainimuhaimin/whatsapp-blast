"""
File uploads: parse CSV/XLSX untuk blast dari file.

Alur:
1. POST /parse (multipart) -> header file dijadikan variabel, dapat upload_id
2. POST /{upload_id}/preview {message, phone_variable} -> render 5 baris pertama
3. POST /{upload_id}/create-campaign {name, message, phone_variable, provider,
   is_test_mode} -> template + campaign draft + recipients + override per baris

Nama variabel dinormalisasi ke pola renderer {{nama_variabel}}:
huruf kecil, spasi/simbol -> underscore (mis. "Nama Lengkap" -> {{nama_lengkap}}).
"""
import csv
import io
import re
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.phone import normalize_phone
from app.models import (
    Campaign,
    CampaignRecipient,
    CampaignRecipientVariable,
    Contact,
    FileUpload,
    Template,
    TemplateVersion,
    User,
)
from app.services import campaign_service, renderer
from app.services.audit_service import write_audit

router = APIRouter(prefix="/file-uploads", tags=["file-uploads"])

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 5000
ALLOWED_EXT = {".csv", ".xlsx", ".xls"}

# Nama kolom yang dianggap sebagai kolom nomor telepon (setelah normalisasi)
PHONE_HINTS = {
    "phone", "telp", "telepon", "nomor", "nomor_hp", "no_hp", "nohp", "hp",
    "whatsapp", "wa", "nomor_telepon", "no_telp", "mobile", "no_wa",
}

_VAR_CLEAN_RE = re.compile(r"[^a-z0-9_]+")


def _ip(request: Request) -> str | None:
    try:
        return request.client.host if request.client else None
    except Exception:
        return None


def _normalize_variable(header: str, used: set[str]) -> str | None:
    """'Nama Lengkap' -> 'nama_lengkap'. None bila header kosong/tak valid."""
    v = _VAR_CLEAN_RE.sub("_", (header or "").strip().lower()).strip("_")
    if not v:
        return None
    if v[0].isdigit():
        v = "_" + v
    base, i = v, 2
    while v in used:  # dua kolom dengan nama sama -> _2, _3, ...
        v = f"{base}_{i}"
        i += 1
    used.add(v)
    return v


def _parse_csv(text: str) -> tuple[list[str], list[list[str]]]:
    # Deteksi delimiter umum (koma / titik-koma / tab)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t"])
    except Exception:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if any((c or "").strip() for c in r)]
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _parse_xlsx(data: bytes) -> tuple[list[str], list[list[str]]]:
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(
            status_code=500, detail="dukungan Excel belum terinstal di server")
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.active
    rows: list[list[str]] = []
    for row in ws.iter_rows(values_only=True):
        vals = ["" if v is None else str(v).strip() for v in row]
        if any(vals):
            rows.append(vals)
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _suggest_phone_variable(variables: list[str]) -> str | None:
    for v in variables:
        if v in PHONE_HINTS:
            return v
    for v in variables:
        if "phone" in v or "telp" in v or v.endswith("_hp") or v == "hp":
            return v
    return None


def _get_upload_or_404(db: Session, upload_id: UUID,
                       user: User) -> FileUpload:
    upload = db.get(FileUpload, upload_id)
    if not upload or (upload.user_id and upload.user_id != user.id):
        raise HTTPException(status_code=404, detail="file upload tidak ditemukan")
    return upload


@router.post("/parse")
def parse_file_upload(file: UploadFile = File(...),
                      db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """Upload & parse CSV/XLSX. Header dijadikan daftar variabel."""
    filename = file.filename or "data"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"format file tidak didukung ({ext or 'tanpa ekstensi'}). "
                   "Pakai .csv atau .xlsx")
    data = file.file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="file terlalu besar (maks 10 MB)")
    if not data:
        raise HTTPException(status_code=400, detail="file kosong")

    if ext == ".csv":
        text = data.decode("utf-8-sig", errors="replace")
        headers, raw_rows = _parse_csv(text)
    else:
        headers, raw_rows = _parse_xlsx(data)

    if not headers:
        raise HTTPException(status_code=400, detail="header tidak ditemukan di file")
    if len(raw_rows) > MAX_ROWS:
        raise HTTPException(
            status_code=400, detail=f"baris terlalu banyak ({len(raw_rows)}). Maks {MAX_ROWS}")

    used: set[str] = set()
    columns: list[dict] = []  # {"header", "variable", "index"} (index = posisi di header asli)
    for idx, h in enumerate(headers):
        var = _normalize_variable(h, used)
        if var:
            columns.append({"header": h.strip(), "variable": var, "index": idx})
    if not columns:
        raise HTTPException(status_code=400, detail="tidak ada kolom valid di file")

    # Samakan panjang baris dengan jumlah header
    n = len(headers)
    rows: list[dict] = []
    for r in raw_rows:
        r = (r + [""] * n)[:n]
        row = {col["variable"]: (r[col["index"]] or "") for col in columns}
        # buang baris yang sepenuhnya kosong
        if any((v or "").strip() for v in row.values()):
            rows.append(row)

    upload = FileUpload(
        filename=filename, columns=columns, rows=rows,
        row_count=len(rows), user_id=user.id,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    variables = [c["variable"] for c in columns]
    write_audit(db, "file_upload.parse", user_id=user.id, entity_type="file_upload",
                entity_id=str(upload.id),
                metadata={"filename": filename, "rows": len(rows)})
    return {
        "upload_id": str(upload.id),
        "filename": filename,
        "columns": columns,
        "row_count": len(rows),
        "phone_variable_suggestion": _suggest_phone_variable(variables),
        "preview": rows[:5],
    }


def _render_previews(upload: FileUpload, message: str,
                     phone_variable: str) -> dict:
    msg_vars = renderer.extract_variables(message or "")
    col_vars = {c["variable"] for c in upload.columns}
    unknown = [v for v in msg_vars if v not in col_vars]
    previews: list[dict] = []
    valid = skipped = 0
    for i, row in enumerate(upload.rows[:5]):
        try:
            phone = normalize_phone(str(row.get(phone_variable, "")))
        except ValueError:
            phone = ""
        values = {k: (v or "") for k, v in row.items()}
        previews.append({
            "row": i + 1,
            "phone": phone,
            "phone_valid": bool(phone),
            "message": renderer.render(message or "", values),
        })
    for row in upload.rows:
        try:
            normalize_phone(str(row.get(phone_variable, "")))
            valid += 1
        except ValueError:
            skipped += 1
    return {
        "previews": previews,
        "unknown_variables": unknown,
        "message_variables": msg_vars,
        "valid_rows": valid,
        "skipped_rows": skipped,
    }


@router.post("/{upload_id}/preview")
def preview_upload(upload_id: UUID, payload: dict,
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """Render 5 baris pertama dengan pesan yang ditulis user."""
    upload = _get_upload_or_404(db, upload_id, user)
    phone_variable = (payload.get("phone_variable") or "").strip()
    col_vars = {c["variable"] for c in upload.columns}
    if phone_variable not in col_vars:
        raise HTTPException(status_code=400, detail="kolom nomor telepon tidak valid")
    return _render_previews(upload, payload.get("message") or "", phone_variable)


@router.post("/{upload_id}/create-campaign")
def create_campaign_from_upload(upload_id: UUID, payload: dict,
                                request: Request,
                                db: Session = Depends(get_db),
                                user: User = Depends(get_current_user)):
    """
    Buat template + campaign draft + recipients dari file upload.
    Tiap baris = 1 penerima; kolom non-telepon = override variabel per penerima.
    """
    upload = _get_upload_or_404(db, upload_id, user)
    name = (payload.get("name") or "").strip()
    message = payload.get("message") or ""
    phone_variable = (payload.get("phone_variable") or "").strip()
    provider = payload.get("provider") or "unofficial"
    is_test_mode = bool(payload.get("is_test_mode"))

    if not name:
        raise HTTPException(status_code=400, detail="nama campaign wajib diisi")
    if not message.strip():
        raise HTTPException(status_code=400, detail="pesan belum ditulis")
    if provider not in {"official", "unofficial"}:
        raise HTTPException(status_code=400, detail="provider tidak valid")
    col_vars = {c["variable"] for c in upload.columns}
    if phone_variable not in col_vars:
        raise HTTPException(status_code=400, detail="kolom nomor telepon tidak valid")

    msg_vars = renderer.extract_variables(message)
    unknown = [v for v in msg_vars if v not in col_vars]

    # Template unik (nama template harus unik)
    base_tname = f"File: {upload.filename[:80]}"
    tname, i = base_tname, 2
    while db.query(Template).filter(Template.name == tname).first():
        tname = f"{base_tname} ({i})"
        i += 1
    template = Template(name=tname, description=f"Dibuat dari upload {upload.filename}")
    db.add(template)
    db.flush()
    version = TemplateVersion(
        template_id=template.id, version_number=1, body=message,
        variables=msg_vars,
    )
    db.add(version)
    db.flush()

    campaign = Campaign(
        name=name, template_version_id=version.id, provider=provider,
        is_test_mode=is_test_mode, status="draft",
    )
    db.add(campaign)
    db.flush()

    # Kolom nama untuk kontak (opsional)
    name_var = next((c["variable"] for c in upload.columns
                     if c["variable"] in {"nama", "name", "nama_lengkap"}), None)

    added = created = matched = 0
    skipped: list[str] = []
    for idx, row in enumerate(upload.rows, start=2):  # baris 1 = header
        try:
            phone = normalize_phone(str(row.get(phone_variable, "")))
        except ValueError:
            skipped.append(f"baris {idx}: nomor tidak valid, dilewati")
            continue
        contact = db.query(Contact).filter(Contact.phone == phone).first()
        row_name = (str(row.get(name_var, "")) if name_var else "").strip()
        if contact:
            matched += 1
            if row_name and contact.name == contact.phone:
                contact.name = row_name
        else:
            created += 1
            contact = Contact(name=row_name or phone, phone=phone)
            db.add(contact)
            db.flush()
        if contact.is_blacklisted:
            skipped.append(f"baris {idx} ({phone}): kontak di-blacklist, dilewati")
            continue
        recipient = CampaignRecipient(
            campaign_id=campaign.id, contact_id=contact.id, phone=phone)
        db.add(recipient)
        db.flush()
        for var in msg_vars:
            if var == phone_variable:
                continue
            db.add(CampaignRecipientVariable(
                recipient_id=recipient.id, variable_name=var,
                value=str(row.get(var, "") or "")))
        added += 1
    db.commit()

    write_audit(db, "file_upload.create_campaign", user_id=user.id,
                entity_type="campaign", entity_id=str(campaign.id),
                metadata={"filename": upload.filename, "added": added,
                          "skipped": len(skipped), "unknown_variables": unknown},
                ip_address=_ip(request))
    return {
        "campaign_id": str(campaign.id),
        "template_name": tname,
        "added": added,
        "created_contacts": created,
        "matched_contacts": matched,
        "skipped": skipped,
        "unknown_variables": unknown,
    }
