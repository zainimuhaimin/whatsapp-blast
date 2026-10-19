"""
Model SQLAlchemy untuk 9 tabel sesuai ERD dokumen desain (section 2),
ditambah kolom hasil konfirmasi riset:
- template_versions: provider_template_name, approval_status, provider_category
- campaigns: provider
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    # default python-side (uuid4) agar create_all portabel; server_default
    # gen_random_uuid() untuk Postgres sesuai dokumen desain.
    return mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_blacklisted: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_contacts_blacklisted", "is_blacklisted"),
        Index("idx_contacts_tag", "tag"),
    )


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["TemplateVersion"]] = relationship(
        back_populates="template", cascade="all, delete-orphan",
        order_by="TemplateVersion.version_number",
    )


class TemplateVersion(Base):
    """Immutable: setiap edit body melahirkan versi baru (tidak pernah di-update)."""

    __tablename__ = "template_versions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("templates.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    # Kolom hasil konfirmasi riset (section 6 dokumen):
    provider_template_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approval_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="draft", server_default=text("'draft'")
    )  # draft | submitted | approved | rejected
    provider_category: Mapped[str | None] = mapped_column(String(24), nullable=True)
    # marketing | utility | authentication | service
    created_at: Mapped[datetime] = _now()

    template: Mapped["Template"] = relationship(back_populates="versions")
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="template_version")

    __table_args__ = (
        UniqueConstraint("template_id", "version_number"),
        Index("idx_template_versions_template", "template_id"),
    )


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    template_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("template_versions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="draft", server_default=text("'draft'")
    )  # draft|review|scheduled|queued|sending|paused|completed|failed|cancelled
    provider: Mapped[str] = mapped_column(
        String(24), nullable=False, default="official", server_default=text("'official'")
    )  # official | unofficial
    is_test_mode: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    template_version: Mapped["TemplateVersion"] = relationship(back_populates="campaigns")
    variable_mappings: Mapped[list["CampaignVariableMapping"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    recipients: Mapped[list["CampaignRecipient"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_campaigns_status", "status"),
        Index("idx_campaigns_send_at", "send_at",
              postgresql_where=text("status = 'scheduled'")),
    )


class CampaignVariableMapping(Base):
    __tablename__ = "campaign_variable_mappings"

    id: Mapped[uuid.UUID] = _uuid_pk()
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    variable_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)  # contact | campaign
    contact_field: Mapped[str | None] = mapped_column(String(32), nullable=True)  # name|phone|tag
    value: Mapped[str | None] = mapped_column(Text, nullable=True)

    campaign: Mapped["Campaign"] = relationship(back_populates="variable_mappings")

    __table_args__ = (
        UniqueConstraint("campaign_id", "variable_name"),
        Index("idx_cvm_campaign", "campaign_id"),
    )


class CampaignRecipient(Base):
    __tablename__ = "campaign_recipients"

    id: Mapped[uuid.UUID] = _uuid_pk()
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id"), nullable=True
    )  # NULL untuk nomor test
    phone: Mapped[str] = mapped_column(String(20), nullable=False)  # snapshot nomor
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default=text("'pending'")
    )  # pending|sent|delivered|read|failed
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="recipients")
    contact: Mapped["Contact | None"] = relationship()
    variable_overrides: Mapped[list["CampaignRecipientVariable"]] = relationship(
        back_populates="recipient", cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # Satu nomor BOLEH muncul berkali-kali dalam satu campaign
        # (mis. satu PIC menerima 2 pesan berbeda untuk 2 pos).
        # Dedup nomor identik tetap dianjurkan di UI, tapi tidak dipaksa DB.
        Index("idx_recipients_campaign_phone", "campaign_id", "phone"),
        Index("idx_recipients_campaign_status", "campaign_id", "status"),
        Index("idx_recipients_provider_msg", "provider_message_id"),
        Index("idx_recipients_retry", "next_retry_at",
              postgresql_where=text("status = 'failed'")),
    )


class CampaignRecipientVariable(Base):
    """
    Override nilai variabel PER PENERIMA (hasil ekstraksi AI per baris,
    atau edit manual). Mengalahkan mapping level campaign & field kontak
    saat render pesan (lihat campaign_service.resolve_values).
    """
    __tablename__ = "campaign_recipient_variables"

    id: Mapped[uuid.UUID] = _uuid_pk()
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign_recipients.id", ondelete="CASCADE"), nullable=False
    )
    variable_name: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)

    recipient: Mapped["CampaignRecipient"] = relationship(
        back_populates="variable_overrides")

    __table_args__ = (
        UniqueConstraint("recipient_id", "variable_name"),
        Index("idx_crv_recipient", "recipient_id"),
    )


class TestNumber(Base):
    __tablename__ = "test_numbers"

    id: Mapped[uuid.UUID] = _uuid_pk()
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = _now()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Nama atribut Python 'meta' -> kolom DB 'metadata' (nama 'metadata'
    # dicadangkan SQLAlchemy Declarative, tidak bisa dipakai sebagai atribut).
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    created_at: Mapped[datetime] = _now()

    user: Mapped["User | None"] = relationship(back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_created", text("created_at DESC")),
        Index("idx_audit_action", "action", text("created_at DESC")),
    )


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
