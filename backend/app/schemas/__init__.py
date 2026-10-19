# Skema Pydantic.
from app.schemas.auth import LoginRequest, UserOut
from app.schemas.campaigns import (
    AIExtractRequest,
    AIExtractResponse,
    AIApplyRecipientsResponse,
    AIApplyRecipientsRequest,
    AIParseRecipientsResponse,
    AIParsedRecipient,
    AIParseRecipientsRequest,
    AIRecipientItem,
    AuditLogOut,
    CampaignCreate,
    CampaignOut,
    CampaignUpdate,
    MappingItem,
    MappingOut,
    MappingsUpdate,
    RecipientOut,
    RecipientsBuildRequest,
    RecipientsBuildResponse,
    ReviewOut,
    ReviewVariableRow,
    SettingOut,
    SettingUpdate,
    StatsOut,
    TestNumberCreate,
    TestNumberOut,
    TestNumberUpdate,
)
from app.schemas.common import PageMeta
from app.schemas.contacts import (
    BlacklistToggle,
    ContactCreate,
    ContactFindOrCreate,
    ContactFindOrCreateResponse,
    ContactOut,
    ContactUpdate,
)
from app.schemas.templates import (
    TemplateCreate,
    TemplateOut,
    TemplateUpdate,
    TemplateVersionOut,
    VersionApprovalUpdate,
    VersionCreate,
)

__all__ = [
    "LoginRequest", "UserOut", "PageMeta",
    "ContactCreate", "ContactUpdate", "ContactOut", "BlacklistToggle",
    "ContactFindOrCreate", "ContactFindOrCreateResponse",
    "TemplateCreate", "TemplateUpdate", "TemplateOut", "TemplateVersionOut",
    "VersionCreate", "VersionApprovalUpdate",
    "CampaignCreate", "CampaignUpdate", "CampaignOut",
    "AIExtractRequest", "AIExtractResponse",
    "AIRecipientItem", "AIParseRecipientsRequest", "AIParsedRecipient",
    "AIParseRecipientsResponse", "AIApplyRecipientsRequest", "AIApplyRecipientsResponse",
    "MappingItem", "MappingsUpdate", "MappingOut",
    "RecipientsBuildRequest", "RecipientsBuildResponse", "RecipientOut",
    "ReviewVariableRow", "ReviewOut", "StatsOut",
    "TestNumberCreate", "TestNumberUpdate", "TestNumberOut",
    "SettingUpdate", "SettingOut", "AuditLogOut",
]
