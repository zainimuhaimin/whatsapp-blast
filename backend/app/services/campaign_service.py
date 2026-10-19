# Service bisnis campaign: validasi confirm & payload review.
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Campaign,
    CampaignRecipient,
    CampaignVariableMapping,
    Contact,
    Setting,
    TemplateVersion,
)
from app.services import renderer

# Tarif default per kategori (IDR per pesan ter-deliver, riset Okt 2026)
DEFAULT_PRICES = {
    "marketing": 627.33,
    "utility": 366.65,
    "authentication": 366.65,
    "service": 356.65,
}

SETTING_DEFAULTS: dict[str, object] = {
    "wa.provider": "official",
    "wa.unofficial_token": "",
    "wa.rate_limit_per_hour": 300,
    "wa.delay_min_sec": 5,
    "wa.delay_max_sec": 15,
    "wa.price_per_message_idr": dict(DEFAULT_PRICES),
    "wa.daily_limit": 250,
    "gemini.model": "gemini-2.0-flash",
    "gemini.api_key": "",  # kosong = pakai GEMINI_API_KEY dari environment
}


def get_setting(db: Session, key: str, default: object = None) -> object:
    """Baca satu setting; fallback ke default bila belum ada."""
    row = db.get(Setting, key)
    if row is not None:
        return row.value
    return SETTING_DEFAULTS.get(key, default)


def get_settings_map(db: Session) -> dict[str, object]:
    """Semua setting efektif (DB + default)."""
    result = dict(SETTING_DEFAULTS)
    for row in db.query(Setting).all():
        result[row.key] = row.value
    return result


def get_mappings(db: Session, campaign_id: UUID) -> dict[str, CampaignVariableMapping]:
    rows = (
        db.query(CampaignVariableMapping)
        .filter(CampaignVariableMapping.campaign_id == campaign_id)
        .all()
    )
    return {r.variable_name: r for r in rows}


def resolve_values(
    db: Session, campaign: Campaign, recipient: CampaignRecipient
) -> dict[str, str]:
    """
    Hitung nilai tiap variabel untuk satu penerima:
    - source 'contact' -> ambil dari field kontak (name/phone/tag); kosong bila tanpa kontak
    - source 'campaign' -> nilai hasil AI / edit manual (sama untuk semua penerima)
    """
    mappings = get_mappings(db, campaign.id)
    contact = None
    if recipient.contact_id:
        contact = db.get(Contact, recipient.contact_id)
    values: dict[str, str] = {}
    for name, m in mappings.items():
        if m.source == "contact":
            values[name] = getattr(contact, m.contact_field, "") if contact and m.contact_field else ""
        else:
            values[name] = m.value or ""
    return values


def render_for_recipient(db: Session, campaign: Campaign, recipient: CampaignRecipient) -> str:
    """Render body template versi ter-pin untuk satu penerima."""
    version: TemplateVersion = campaign.template_version
    return renderer.render(version.body, resolve_values(db, campaign, recipient))


def recipient_count(db: Session, campaign_id: UUID) -> int:
    return (
        db.query(func.count(CampaignRecipient.id))
        .filter(CampaignRecipient.campaign_id == campaign_id)
        .scalar()
        or 0
    )


def validate_confirm(db: Session, campaign: Campaign) -> list[str]:
    """
    Validasi sebelum confirm (sesuai dokumen):
    (a) provider official -> versi template harus approved
    (b) minimal 1 penerima
    (c) semua variabel template ter-mapping
    (d) jumlah penerima <= wa.daily_limit
    """
    errors: list[str] = []
    version: TemplateVersion = campaign.template_version
    mappings = get_mappings(db, campaign.id)

    # (a) approval template untuk jalur resmi
    if campaign.provider == "official" and version.approval_status != "approved":
        errors.append(
            f"jalur resmi wajib memakai template yang di-approve Meta "
            f"(status saat ini: '{version.approval_status}')"
        )

    # (b) minimal 1 penerima
    total = recipient_count(db, campaign.id)
    if total < 1:
        errors.append("campaign belum memiliki penerima (tambahkan via recipients)")

    # (c) semua variabel ter-mapping lengkap
    for var in version.variables:
        m = mappings.get(var)
        if m is None:
            errors.append(f"variabel '{{{{{var}}}}}' belum dipetakan")
            continue
        if m.source == "contact" and not m.contact_field:
            errors.append(f"variabel '{{{{{var}}}}}' sumber kontak tapi field belum dipilih")
        elif m.source == "campaign" and not (m.value or "").strip():
            errors.append(f"variabel '{{{{{var}}}}}' sumber campaign tapi nilainya kosong")

    # (d) batas tier harian nomor
    daily_limit = int(get_setting(db, "wa.daily_limit", 250) or 250)
    if total > daily_limit:
        errors.append(
            f"jumlah penerima ({total}) melebihi batas tier harian ({daily_limit}); "
            "bagi campaign atau naikkan tier nomor"
        )
    return errors


def estimate_duration_text(total: int, rate_limit_per_hour: int) -> str:
    """Rumus estimasi durasi dari dokumen: maks(n*10 dtk, n/rate_limit jam)."""
    if total <= 0:
        return "± 0 menit"
    eta_detik = total * 10  # rata-rata delay 5-15 dtk
    batas_detik = (total / rate_limit_per_hour * 3600) if rate_limit_per_hour > 0 else 0
    detik = max(eta_detik, batas_detik)
    menit = detik / 60
    if menit < 60:
        return f"± {max(1, round(menit))} menit"
    jam = menit / 60
    return f"± {jam:.1f} jam"


def estimate_cost(db: Session, campaign: Campaign, total: int) -> tuple[float, str]:
    """
    Estimasi biaya: official = total x tarif kategori; unofficial = Rp 0.
    Return (biaya_idr, catatan).
    """
    if campaign.provider == "unofficial":
        return 0.0, "jalur non-resmi (Baileys self-hosted): Rp 0"
    version: TemplateVersion = campaign.template_version
    prices = get_setting(db, "wa.price_per_message_idr", DEFAULT_PRICES) or DEFAULT_PRICES
    category = version.provider_category or "marketing"
    tarif = float(prices.get(category, prices.get("marketing", 0)))
    return total * tarif, (
        f"{total} penerima x Rp {tarif:,.2f} (kategori {category}, tarif Meta Indonesia)"
    )


def build_review(db: Session, campaign: Campaign) -> dict:
    """Susun payload GET /api/campaigns/{id}/review sesuai dokumen."""
    version: TemplateVersion = campaign.template_version
    mappings = get_mappings(db, campaign.id)
    total = recipient_count(db, campaign.id)

    recipients = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == campaign.id)
        .order_by(CampaignRecipient.created_at)
        .limit(5)
        .all()
    )

    variables_rows = []
    for var in version.variables:
        m = mappings.get(var)
        sample_values = []
        for r in recipients:
            vals = resolve_values(db, campaign, r)
            v = vals.get(var, "")
            if v not in sample_values:
                sample_values.append(v)
        variables_rows.append(
            {
                "variable_name": var,
                "source": m.source if m else None,
                "contact_field": m.contact_field if m else None,
                "campaign_value": m.value if m and m.source == "campaign" else None,
                "sample_values": sample_values[:5],
            }
        )

    sample_messages = [render_for_recipient(db, campaign, r) for r in recipients]

    # Pratinjau penerima × nilai variabel (maks 50 baris agar payload ringan)
    preview_rows = []
    for r in (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == campaign.id)
        .order_by(CampaignRecipient.created_at)
        .limit(50)
        .all()
    ):
        preview_rows.append(
            {
                "id": r.id,
                "name": r.contact.name if r.contact else None,
                "phone": r.phone,
                "values": resolve_values(db, campaign, r),
            }
        )

    rate_limit = int(get_setting(db, "wa.rate_limit_per_hour", 300) or 300)
    cost, cost_note = estimate_cost(db, campaign, total)

    return {
        "campaign_id": campaign.id,
        "total_recipients": total,
        "variables": variables_rows,
        "recipient_preview": preview_rows,
        "sample_messages": sample_messages,
        "estimated_duration": estimate_duration_text(total, rate_limit),
        "estimated_cost_idr": cost,
        "estimated_cost_note": cost_note,
        "validation_errors": validate_confirm(db, campaign),
        "is_test_mode": campaign.is_test_mode,
        "provider": campaign.provider,
    }
