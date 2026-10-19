# Skema template + versi template.
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    body: str = Field(min_length=1)


class TemplateUpdate(BaseModel):
    # Hanya name/description; body diubah via versi baru (immutable).
    name: str | None = Field(default=None, max_length=128)
    description: str | None = None


class VersionCreate(BaseModel):
    body: str = Field(min_length=1)
    provider_template_name: str | None = Field(default=None, max_length=128)
    provider_category: str | None = Field(
        default=None, description="marketing|utility|authentication|service"
    )
    approval_status: str | None = Field(
        default=None, description="draft|submitted|approved|rejected"
    )


class VersionApprovalUpdate(BaseModel):
    provider_template_name: str | None = Field(default=None, max_length=128)
    provider_category: str | None = None
    approval_status: str | None = Field(default=None, description="draft|submitted|approved|rejected")


class TemplateVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_id: UUID
    version_number: int
    body: str
    variables: list[str]
    provider_template_name: str | None
    approval_status: str
    provider_category: str | None
    created_at: datetime


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    latest_version: TemplateVersionOut | None = None
