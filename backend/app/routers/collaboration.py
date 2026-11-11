"""Sprint 2 ticket collaboration: assignment, replies, editing, history, uploads, notifications."""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Attachment, Comment, Notification, Role, Status, Ticket,
    TicketHistory, User, utcnow
)
from ..schemas import (
    AssignmentIn, CommentCreate, CommentOut, NotificationOut,
    TicketEditIn, TicketOut, UserBrief
)
from ..security import get_current_user, require_roles

router = APIRouter(prefix="/api", tags=["ticket collaboration"])
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".txt", ".docx", ".xlsx", ".csv"}


def _can_access(user: User, ticket: Ticket) -> bool:
    if user.role in (Role.ADMIN, Role.MANAGER):
        return True
    if user.role == Role.AGENT:
        return ticket.assigned_to_id == user.id
    return ticket.created_by_id == user.id


def _ticket_or_404(db: Session, ticket_id: int, user: User) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or not _can_access(user, ticket):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return ticket


def _history(db: Session, ticket_id: int, actor_id: int, action: str, details: str = ""):
    db.add(TicketHistory(ticket_id=ticket_id, actor_id=actor_id, action=action, details=details))


def _notify(db: Session, user_id: int | None, ticket_id: int, message: str):
    if user_id is not None:
        db.add(Notification(user_id=user_id, ticket_id=ticket_id, message=message))


@router.patch("/tickets/{ticket_id}/assignment", response_model=TicketOut)
def assign_ticket(
    ticket_id: int,
    body: AssignmentIn,
    db: Session = Depends(get_db),
    manager: User = Depends(require_roles(Role.MANAGER, Role.ADMIN)),
):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    agent = db.get(User, body.agent_id)
    if agent is None or not agent.is_active or agent.role != Role.AGENT:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Select an active support agent")
    previous_id = ticket.assigned_to_id
    ticket.assigned_to_id = agent.id
    ticket.updated_at = utcnow()
    _history(db, ticket.id, manager.id, "assigned", f"Assigned to {agent.email}; previous agent id: {previous_id}")
    _notify(db, agent.id, ticket.id, f"Ticket #{ticket.id} has been assigned to you.")
    if previous_id and previous_id != agent.id:
        _notify(db, previous_id, ticket.id, f"Ticket #{ticket.id} has been reassigned.")
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/tickets/{ticket_id}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(
    ticket_id: int,
    body: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = _ticket_or_404(db, ticket_id, user)
    comment = Comment(ticket_id=ticket.id, author_id=user.id, body=body.body.strip())
    db.add(comment)
    _history(db, ticket.id, user.id, "comment_added", f"Comment added by {user.email}")
    recipient_id = ticket.created_by_id if user.id != ticket.created_by_id else ticket.assigned_to_id
    _notify(db, recipient_id, ticket.id, f"New response on ticket #{ticket.id}.")
    db.commit()
    db.refresh(comment)
    return comment


@router.get("/tickets/{ticket_id}/comments", response_model=list[CommentOut])
def list_comments(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ticket = _ticket_or_404(db, ticket_id, user)
    return db.scalars(select(Comment).where(Comment.ticket_id == ticket.id).order_by(Comment.created_at, Comment.id)).all()


@router.patch("/tickets/{ticket_id}", response_model=TicketOut)
def edit_ticket(
    ticket_id: int,
    body: TicketEditIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.created_by_id != user.id or user.role != Role.END_USER:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    if ticket.status != Status.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only open tickets can be edited")
    from ..models import Category
    if db.get(Category, body.category_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown category")
    ticket.title = body.title.strip()
    ticket.description = body.description.strip()
    ticket.category_id = body.category_id
    ticket.updated_at = utcnow()
    _history(db, ticket.id, user.id, "ticket_edited", "Requester updated ticket details")
    _notify(db, ticket.assigned_to_id, ticket.id, f"Ticket #{ticket.id} details were updated.")
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/tickets/{ticket_id}/close", response_model=TicketOut)
def close_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    agent: User = Depends(require_roles(Role.AGENT, Role.MANAGER, Role.ADMIN)),
):
    ticket = _ticket_or_404(db, ticket_id, agent)
    if ticket.status not in (Status.RESOLVED, Status.IN_PROGRESS, Status.ON_HOLD):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ticket must be resolved or actively worked before closing")
    ticket.status = Status.CLOSED
    ticket.resolved_at = ticket.resolved_at or utcnow()
    ticket.updated_at = utcnow()
    _history(db, ticket.id, agent.id, "closed", "Ticket closed")
    _notify(db, ticket.created_by_id, ticket.id, f"Ticket #{ticket.id} was closed.")
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/tickets/{ticket_id}/reopen", response_model=TicketOut)
def reopen_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    agent: User = Depends(require_roles(Role.AGENT, Role.MANAGER, Role.ADMIN)),
):
    ticket = _ticket_or_404(db, ticket_id, agent)
    if ticket.status not in (Status.RESOLVED, Status.CLOSED):
        raise HTTPException(status.HTTP_409_CONFLICT, "Only resolved or closed tickets can be reopened")
    ticket.status = Status.IN_PROGRESS
    ticket.resolved_at = None
    ticket.updated_at = utcnow()
    _history(db, ticket.id, agent.id, "reopened", "Ticket reopened")
    _notify(db, ticket.created_by_id, ticket.id, f"Ticket #{ticket.id} was reopened.")
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/tickets/{ticket_id}/history")
def ticket_history(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ticket = _ticket_or_404(db, ticket_id, user)
    rows = db.scalars(select(TicketHistory).where(TicketHistory.ticket_id == ticket.id).order_by(TicketHistory.created_at, TicketHistory.id)).all()
    return [{
        "id": row.id, "action": row.action, "details": row.details,
        "actor_id": row.actor_id, "created_at": row.created_at
    } for row in rows]


@router.post("/tickets/{ticket_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    ticket_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = _ticket_or_404(db, ticket_id, user)
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "File type is not allowed")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File is empty or exceeds the upload limit")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{extension}"
    (UPLOAD_DIR / stored_name).write_bytes(data)
    record = Attachment(
        ticket_id=ticket.id, uploader_id=user.id,
        original_name=Path(file.filename or "upload").name[:255],
        stored_name=stored_name,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(data),
    )
    db.add(record)
    _history(db, ticket.id, user.id, "attachment_added", f"Uploaded {record.original_name}")
    recipient_id = ticket.created_by_id if user.id != ticket.created_by_id else ticket.assigned_to_id
    _notify(db, recipient_id, ticket.id, f"A file was attached to ticket #{ticket.id}.")
    db.commit()
    db.refresh(record)
    return {"id": record.id, "filename": record.original_name, "size_bytes": record.size_bytes, "created_at": record.created_at}


@router.get("/tickets/{ticket_id}/attachments")
def list_attachments(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ticket = _ticket_or_404(db, ticket_id, user)
    rows = db.scalars(select(Attachment).where(Attachment.ticket_id == ticket.id).order_by(Attachment.created_at)).all()
    return [{"id": r.id, "filename": r.original_name, "size_bytes": r.size_bytes, "content_type": r.content_type, "created_at": r.created_at} for r in rows]


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc())).all()


@router.patch("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification


@router.get("/tickets/{ticket_id}/attachments/{attachment_id}/download")
def download_attachment(
    ticket_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = _ticket_or_404(db, ticket_id, user)
    record = db.get(Attachment, attachment_id)
    if record is None or record.ticket_id != ticket.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    path = (UPLOAD_DIR / record.stored_name).resolve()
    if path.parent != UPLOAD_DIR.resolve() or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment file is unavailable")
    return FileResponse(
        path,
        media_type=record.content_type,
        filename=record.original_name,
    )
