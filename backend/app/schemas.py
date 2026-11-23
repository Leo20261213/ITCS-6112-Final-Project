from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import EventKind, Priority, Role, Status


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str


class RegisterIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserAdminUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=255)


class CategoryOut(CategoryIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=5000)
    # Leave out to let the help desk categorize the ticket automatically.
    category_id: int | None = None
    priority: Priority = Priority.MEDIUM


class TicketStatusUpdate(BaseModel):
    status: Status


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    priority: Priority
    status: Status
    category: CategoryOut
    created_by: UserBrief
    assigned_to: UserBrief | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class TicketUpdate(BaseModel):
    """US-10: the only fields an end user may change. Anything else (status, assignee,
    requester, ...) is rejected rather than silently applied."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=10, max_length=5000)
    category_id: int | None = None
    priority: Priority | None = None


class AssignmentUpdate(BaseModel):
    """US-08: agent_id = None unassigns the ticket."""

    agent_id: int | None


class AgentWorkload(UserBrief):
    active_tickets: int


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    body: str
    author: UserBrief
    author_role: Role
    created_at: datetime


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: EventKind
    detail: str
    actor: UserBrief | None
    created_at: datetime


class AttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    size: int
    uploaded_by: UserBrief
    created_at: datetime


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int | None
    message: str
    is_read: bool
    created_at: datetime


class NotificationList(BaseModel):
    unread: int
    items: list[NotificationOut]


class AttachmentRules(BaseModel):
    max_bytes: int
    max_per_ticket: int
    allowed_extensions: list[str]


class MetaOut(BaseModel):
    priorities: list[Priority]
    statuses: list[Status]
    roles: list[Role]
    status_transitions: dict[Status, list[Status]]
    editable_statuses: list[Status]
    attachment_rules: AttachmentRules


# Sprint 3 ---------------------------------------------------------------
class AiMeta(BaseModel):
    """Who generated an AI result, so the UI can label it (US-21 transparency)."""

    source: str  # claude | local
    model: str | None
    notice: str | None = None


class CategorySuggestion(BaseModel):
    id: int
    name: str
    confidence: float
    reason: str
    matches_current: bool


class PrioritySuggestion(BaseModel):
    value: Priority
    confidence: float
    reason: str
    signals: list[str]
    matches_current: bool


class TriageOut(AiMeta):
    """US-15 and US-16: suggestions for the agent to review; nothing is changed."""

    category: CategorySuggestion | None = None
    priority: PrioritySuggestion | None = None


class ClassificationUpdate(BaseModel):
    """Staff apply a category and/or priority (e.g. accepting an AI suggestion)."""

    model_config = ConfigDict(extra="forbid")

    category_id: int | None = None
    priority: Priority | None = None
    ai_assisted: bool = False


class SummaryOut(AiMeta):
    summary: str
    key_points: list[str]
    next_step: str
    message_count: int


class ReplyRequest(BaseModel):
    instructions: str = Field(default="", max_length=300)


class ReplyOut(AiMeta):
    reply: str


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatTurn] = Field(min_length=1, max_length=20)


class ArticleRef(BaseModel):
    id: int
    title: str


class TicketDraft(BaseModel):
    title: str
    description: str
    category_id: int | None


class ChatOut(AiMeta):
    answer: str
    confident: bool
    escalate: bool
    sources: list[ArticleRef]
    ticket_suggestion: TicketDraft | None


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str


class AiFeatures(BaseModel):
    enabled: bool
    category: bool
    priority: bool
    summary: bool
    reply: bool
    chatbot: bool
    intake: bool


class AiSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled: bool
    provider: str
    model: str
    category_suggestions: bool
    priority_suggestions: bool
    summaries: bool
    reply_suggestions: bool
    chatbot: bool
    auto_triage: bool
    share_personal_data: bool
    reply_guidance: str
    updated_at: datetime | None
    updated_by: UserBrief | None


class AiSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    provider: str | None = Field(default=None, pattern="^(auto|claude|local)$")
    model: str | None = None
    category_suggestions: bool | None = None
    priority_suggestions: bool | None = None
    summaries: bool | None = None
    reply_suggestions: bool | None = None
    chatbot: bool | None = None
    auto_triage: bool | None = None
    share_personal_data: bool | None = None
    reply_guidance: str | None = Field(default=None, max_length=500)


class AiAdminOut(BaseModel):
    settings: AiSettingsOut
    models: dict[str, str]
    claude_credentials_detected: bool


class AiUsageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    feature: str
    user: UserBrief
    ticket_id: int | None
    source: str
    model: str | None
    outcome: str
    note: str
    latency_ms: int
    created_at: datetime


class AiUsageReport(BaseModel):
    totals: dict[str, int]
    items: list[AiUsageOut]
