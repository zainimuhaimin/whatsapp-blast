# Skema kontak.
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.phone import normalize_phone


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    phone: str = Field(min_length=1, max_length=20)
    tag: str | None = Field(default=None, max_length=64)
    notes: str | None = None

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)


class ContactUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    phone: str = Field(min_length=1, max_length=20)
    tag: str | None = Field(default=None, max_length=64)
    notes: str | None = None

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)


class BlacklistToggle(BaseModel):
    is_blacklisted: bool


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str
    tag: str | None
    notes: str | None
    is_blacklisted: bool
    created_at: datetime
    updated_at: datetime


class ContactFindOrCreate(BaseModel):
    """Input nomor cepat (mis. nomor PIC): cari berdasar nomor yang
    dinormalisasi, buat baru otomatis bila belum ada."""
    phone: str = Field(min_length=1, max_length=20)
    name: str | None = Field(default=None, max_length=128)
    tag: str | None = Field(default=None, max_length=64)
    notes: str | None = None

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)


class ContactFindOrCreateResponse(BaseModel):
    contact: ContactOut
    created: bool
