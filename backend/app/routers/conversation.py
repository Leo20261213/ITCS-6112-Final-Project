"""US-09: As a user or an agent, I want to exchange messages on a ticket so that I can
clarify and resolve an issue.
US-12: As a support agent, I want to view ticket activity history so that I can
understand previous actions.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..access import get_visible_ticket
from ..activity import record
from ..database import get_db
from ..models import EventKind, Status, TicketEvent, TicketMessage, User
from ..schemas import EventOut, MessageIn, MessageOut
from ..security import get_current_user

router = APIRouter(prefix="/api/tickets", tags=["conversation"])


@router.get("/{ticket_id}/messages", response_model=list[MessageOut])
def list_messages(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_visible_ticket(db, ticket_id, user)
    return db.scalars(
        select(TicketMessage)
        .where(TicketMessage.ticket_id == ticket_id)
        .order_by(TicketMessage.created_at, TicketMessage.id)
    ).all()


@router.post("/{ticket_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def post_message(
    ticket_id: int,
    body: MessageIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ticket = get_visible_ticket(db, ticket_id, user)
    if ticket.status == Status.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This ticket is closed. Reopen it to continue the conversation.")
    text = body.body.strip()
    if not text:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Message cannot be empty")
    message = TicketMessage(ticket_id=ticket.id, author_id=user.id, body=text)
    db.add(message)
    preview = text if len(text) <= 80 else text[:77] + "…"
    record(
        db, ticket, user, EventKind.MESSAGE, f"{user.full_name} posted a message",
        message=f"{user.full_name} replied on ticket #{ticket.id} “{ticket.title}”: {preview}",
    )
    db.commit()
    db.refresh(message)
    return message


@router.get("/{ticket_id}/history", response_model=list[EventOut])
def ticket_history(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Chronological record of everything that has happened to a ticket."""
    get_visible_ticket(db, ticket_id, user)
    return db.scalars(
        select(TicketEvent).where(TicketEvent.ticket_id == ticket_id).order_by(TicketEvent.created_at, TicketEvent.id)
    ).all()
