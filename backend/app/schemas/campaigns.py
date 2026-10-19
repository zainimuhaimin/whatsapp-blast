# Skema campaign, mapping, recipients, review, test numbers, settings, audit.
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.phone import normalize_phone

CONTACT_FIELDS = {"name", "phone", "tag"}


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    template_version_id: UUID
    provider: str = Field(default="official", description="official|unofficial")
    is_test_mode: bool = False
    send_at: datetime | None = None

    @field_validator("provider")
    @classmethod
    def _provider(cls, v: str) -> str:
        if v not in {"official", "unofficial"}:
            raise ValueError("provider harus 'official' atau 'unofficial'")
        return v


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    template_version_id: UUID | None = Field(
        default=None, description="ganti template (draft saja; mapping & penerima ikut direset)")
    send_at: datetime | None = None
    is_test_mode: bool | None = None
    provider: str | None = None

    @field_validator("provider")
    @classmethod
    def _provider(cls, v: str | None) -> str | None:
        if v is not None and v not in {"official", "unofficial"}:
            raise ValueError("provider harus 'official' atau 'unofficial'")
        return v


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    template_version_id: UUID
    status: str
    provider: str
    is_test_mode: bool
    send_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AIExtractRequest(BaseModel):
    input_text: str = Field(min_length=1)


class AIExtractResponse(BaseModel):
    values: dict[str, str]
    ai_available: bool


class MappingItem(BaseModel):
    variable_name: str = Field(min_length=1, max_length=64)
    source: str = Field(description="contact|campaign")
    contact_field: str | None = Field(default=None, description="name|phone|tag")
    value: str | None = None

    @field_validator("source")
    @classmethod
    def _source(cls, v: str) -> str:
        if v not in {"contact", "campaign"}:
            raise ValueError("source harus 'contact' atau 'campaign'")
        return v

    @field_validator("contact_field")
    @classmethod
    def _contact_field(cls, v: str | None) -> str | None:
        if v is not None and v not in CONTACT_FIELDS:
            raise ValueError(f"contact_field harus salah satu dari {sorted(CONTACT_FIELDS)}")
        return v


class MappingsUpdate(BaseModel):
    mappings: list[MappingItem]


class MappingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    variable_name: str
    source: str
    contact_field: str | None
    value: str | None


class RecipientsBuildRequest(BaseModel):
    contact_ids: list[UUID] = Field(default_factory=list)


class RecipientsBuildResponse(BaseModel):
    added: int
    skipped_blacklisted: int
    skipped_duplicate: int
    total: int


class RecipientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    contact_id: UUID | None
    contact_name: str | None = None
    phone: str
    status: str
    retry_count: int
    next_retry_at: datetime | None
    last_error: str | None
    provider_message_id: str | None
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None


class ReviewVariableRow(BaseModel):
    variable_name: str
    source: str
    contact_field: str | None = None
    campaign_value: str | None = None
    sample_values: list[str] = Field(default_factory=list)


class ReviewRecipientRow(BaseModel):
    """Satu baris tabel pratinjau penerima × nilai variabel."""
    id: UUID
    name: str | None = None
    phone: str
    values: dict[str, str] = Field(default_factory=dict)


class ReviewOut(BaseModel):
    campaign_id: UUID
    total_recipients: int
    variables: list[ReviewVariableRow]
    recipient_preview: list[ReviewRecipientRow] = Field(
        default_factory=list, description="maks 50 baris pertama untuk tabel pratinjau")
    sample_messages: list[str]
    estimated_duration: str
    estimated_cost_idr: float
    estimated_cost_note: str
    validation_errors: list[str]
    is_test_mode: bool
    provider: str


class StatsOut(BaseModel):
    campaign_id: UUID
    pending: int = 0
    sent: int = 0
    delivered: int = 0
    read: int = 0
    failed: int = 0
    total: int = 0


class TestNumberCreate(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    phone: str = Field(min_length=1, max_length=20)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)


class TestNumberUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return normalize_phone(v) if v is not None else v


class TestNumberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label: str
    phone: str
    is_active: bool
    created_at: datetime


class SettingUpdate(BaseModel):
    value: object


class SettingOut(BaseModel):
    key: str
    value: object
    is_secret: bool = False  # True -> value hanya pratinjau tersamar, bukan nilai asli


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: UUID | None
    username: str | None = None
    action: str
    entity_type: str | None
    entity_id: str | None
    metadata: dict | None
    ip_address: str | None
    created_at: datetime
