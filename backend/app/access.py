"""Ticket-level authorization shared by every ticket-related router (US-02)."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .models import Role, Ticket, User

STAFF_ROLES = (Role.AGENT, Role.MANAGER, Role.ADMIN)
OVERSIGHT_ROLES = (Role.MANAGER, Role.ADMIN)


def can_view(user: User, ticket: Ticket) -> bool:
    """Managers and administrators see every ticket, agents see tickets assigned to them,
    end users see tickets they submitted."""
    if user.role in OVERSIGHT_ROLES:
        return True
    if user.role == Role.AGENT:
        return ticket.assigned_to_id == user.id
    return ticket.created_by_id == user.id


def get_visible_ticket(db: Session, ticket_id: int, user: User) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    # 404 rather than 403 so ticket IDs owned by others are not disclosed.
    if ticket is None or not can_view(user, ticket):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return ticket
