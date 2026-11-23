"""Sprint 3 AI assistance.

US-15: As a support agent, I want AI to suggest ticket categories so that requests can be classified faster.
US-16: As a support agent, I want AI to identify possible urgency and priority so that critical requests receive attention.
US-17: As a support agent, I want an AI-generated ticket summary so that I can understand lengthy conversations quickly.
US-18: As a support agent, I want AI-generated response suggestions so that I can draft replies more efficiently.
US-19: As an end-user, I want an AI chatbot to answer common questions so that I can find help quickly.
US-21: As an administrator, I want to configure AI assistance options so that AI features can be managed responsibly.

Every AI output an agent sees is a suggestion: agents apply category/priority changes and send replies
themselves. The one automatic step is intake (routers/tickets.py): a new ticket is categorized and routed
to an agent as it arrives, each decision is written to the ticket history with its reason, and staff can
change either afterwards. Administrators can turn intake off.
"""
import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..access import STAFF_ROLES, get_visible_ticket
from ..activity import record
from ..ai import claude, service
from ..database import get_db
from ..models import AiUsage, Category, EventKind, HelpArticle, Role, Status, User
from ..schemas import (
    AiAdminOut,
    AiFeatures,
    AiSettingsOut,
    AiSettingsUpdate,
    AiUsageReport,
    ArticleOut,
    ChatOut,
    ChatRequest,
    ClassificationUpdate,
    ReplyOut,
    ReplyRequest,
    SummaryOut,
    TicketOut,
    TriageOut,
)
from ..security import get_current_user, require_roles

router = APIRouter(prefix="/api", tags=["ai"])
staff_only = require_roles(*STAFF_ROLES)
admin_only = require_roles(Role.ADMIN)

PRIORITY_LABELS = {"low": "Low", "medium": "Medium", "high": "High", "critical": "Critical"}


def _meta(result: service.AiResult) -> dict:
    return {"source": result.source, "model": result.model, "notice": result.notice}


@router.get("/ai/features", response_model=AiFeatures)
def ai_features(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Which AI features are switched on, so the interface only offers those (US-21)."""
    s = service.get_settings(db)
    return AiFeatures(enabled=s.enabled, **{f: service.feature_enabled(s, f) for f in service.FEATURES})


# US-15 / US-16 ---------------------------------------------------------------
@router.post("/tickets/{ticket_id}/ai/triage", response_model=TriageOut)
def suggest_triage(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(staff_only)):
    ticket = get_visible_ticket(db, ticket_id, user)
    result = service.triage(db, user, ticket)
    return TriageOut(**_meta(result), **result.data)


@router.patch("/tickets/{ticket_id}/classification", response_model=TicketOut)
def classify_ticket(
    ticket_id: int,
    body: ClassificationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(staff_only),
):
    """Staff set the category and/or priority, for example by accepting an AI suggestion."""
    ticket = get_visible_ticket(db, ticket_id, user)
    if ticket.status == Status.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Reopen the ticket before reclassifying it")
    changes = []
    if body.category_id is not None and body.category_id != ticket.category_id:
        category = db.get(Category, body.category_id)
        if category is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown category")
        changes.append(f"category from {ticket.category.name} to {category.name}")
        ticket.category = category
    if body.priority is not None and body.priority != ticket.priority:
        changes.append(f"priority from {PRIORITY_LABELS[ticket.priority.value]} to {PRIORITY_LABELS[body.priority.value]}")
        ticket.priority = body.priority
    if changes:
        suffix = " (AI suggestion accepted)" if body.ai_assisted else ""
        record(db, ticket, user, EventKind.EDITED, f"Changed the {' and '.join(changes)}{suffix}")
        db.commit()
        db.refresh(ticket)
    return ticket


# US-17 ------------------------------------------------------------------------
@router.post("/tickets/{ticket_id}/ai/summary", response_model=SummaryOut)
def summarize_ticket(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(staff_only)):
    ticket = get_visible_ticket(db, ticket_id, user)
    result = service.summarize(db, user, ticket)
    return SummaryOut(**_meta(result), **result.data, message_count=result.extra["message_count"])


# US-18 ------------------------------------------------------------------------
@router.post("/tickets/{ticket_id}/ai/reply", response_model=ReplyOut)
def suggest_reply(
    ticket_id: int,
    body: ReplyRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(staff_only),
):
    ticket = get_visible_ticket(db, ticket_id, user)
    if ticket.status == Status.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This ticket is closed. Reopen it before replying.")
    result = service.draft_reply(db, user, ticket, (body.instructions if body else "").strip())
    return ReplyOut(**_meta(result), **result.data)


# US-19 ------------------------------------------------------------------------
@router.post("/assistant/chat", response_model=ChatOut)
def assistant_chat(body: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    turns = [t.model_dump() for t in body.messages]
    if turns[0]["role"] != "user" or turns[-1]["role"] != "user":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The conversation must start and end with a user message")
    if any(a["role"] == b["role"] for a, b in zip(turns, turns[1:])):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Messages must alternate between user and assistant")
    if not turns[-1]["content"].strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Message cannot be empty")
    result = service.chat(db, user, turns)
    return ChatOut(**_meta(result), **result.data)


@router.get("/help/articles", response_model=list[ArticleOut])
def list_articles(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(HelpArticle).order_by(HelpArticle.title)).all()


@router.get("/help/articles/{article_id}", response_model=ArticleOut)
def get_article(article_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    article = db.get(HelpArticle, article_id)
    if article is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")
    return article


# US-21 ------------------------------------------------------------------------
def _credentials_detected() -> bool:
    return any(os.getenv(v) for v in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE")) or os.path.isdir(
        os.path.expanduser("~/.config/anthropic")
    )


def _admin_view(db: Session) -> AiAdminOut:
    return AiAdminOut(
        settings=AiSettingsOut.model_validate(service.get_settings(db)),
        models=claude.MODELS,
        claude_credentials_detected=_credentials_detected(),
    )


@router.get("/admin/ai-settings", response_model=AiAdminOut)
def get_ai_settings(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return _admin_view(db)


@router.put("/admin/ai-settings", response_model=AiAdminOut)
def update_ai_settings(body: AiSettingsUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    settings = service.get_settings(db)
    changes = body.model_dump(exclude_unset=True)
    if "model" in changes and changes["model"] not in claude.MODELS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Model must be one of: {', '.join(claude.MODELS)}")
    if changes.get("reply_guidance") is not None:
        changes["reply_guidance"] = changes["reply_guidance"].strip()
    for key, value in changes.items():
        if value is not None:
            setattr(settings, key, value)
    settings.updated_by_id = admin.id
    db.commit()
    return _admin_view(db)


@router.get("/admin/ai-usage", response_model=AiUsageReport)
def ai_usage(
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
    limit: int = Query(50, ge=1, le=200),
):
    totals = {f"{source}:{outcome}": n for source, outcome, n in db.execute(
        select(AiUsage.source, AiUsage.outcome, func.count()).group_by(AiUsage.source, AiUsage.outcome)
    )}
    totals["all"] = sum(totals.values())
    items = db.scalars(select(AiUsage).order_by(AiUsage.created_at.desc(), AiUsage.id.desc()).limit(limit)).all()
    return AiUsageReport(totals=totals, items=items)
