"""Ticket lifecycle for Sprint 1.

US-03: As an end-user, I want to submit a support ticket so that I can request assistance.
US-04: As an end-user, I want to view my submitted tickets so that I can monitor their progress.
US-05: As a user, I want tickets to have categories, priorities, and statuses so that requests are organized.
US-06: As a support agent, I want to view tickets assigned to me so that I can manage my workload.
US-07: As a support agent, I want to update ticket statuses so that users can track progress.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Priority, Role, Status, Ticket, User
from ..schemas import CategoryOut, MetaOut, TicketCreate, TicketOut, TicketStatusUpdate
from ..security import get_current_user, require_roles

router = APIRouter(prefix="/api", tags=["tickets"])

# Statuses an agent may move a ticket to in Sprint 1. Closing and reopening are US-11 (Sprint 2).
STATUS_TRANSITIONS: dict[Status, list[Status]] = {
    Status.OPEN: [Status.IN_PROGRESS, Status.ON_HOLD, Status.RESOLVED],
    Status.IN_PROGRESS: [Status.ON_HOLD, Status.RESOLVED],
    Status.ON_HOLD: [Status.IN_PROGRESS, Status.RESOLVED],
    Status.RESOLVED: [],
    Status.CLOSED: [],
}
ACTIVE_STATUSES = (Status.OPEN, Status.IN_PROGRESS, Status.ON_HOLD)


def pick_agent(db: Session) -> User | None:
    """Auto-assign to the active agent with the fewest active tickets.
    Manual manager assignment arrives with US-08 in Sprint 2."""
    workload = (
        select(User, func.count(Ticket.id).label("load"))
        .outerjoin(Ticket, (Ticket.assigned_to_id == User.id) & Ticket.status.in_(ACTIVE_STATUSES))
        .where(User.role == Role.AGENT, User.is_active.is_(True))
        .group_by(User.id)
        .order_by("load", User.id)
    )
    row = db.execute(workload).first()
    return row[0] if row else None


def can_view(user: User, ticket: Ticket) -> bool:
    if user.role == Role.ADMIN:
        return True
    if user.role == Role.AGENT:
        return ticket.assigned_to_id == user.id
    return ticket.created_by_id == user.id


@router.get("/meta", response_model=MetaOut)
def meta(_: User = Depends(get_current_user)):
    return MetaOut(
        priorities=list(Priority),
        statuses=list(Status),
        roles=list(Role),
        status_transitions=STATUS_TRANSITIONS,
    )


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Category).order_by(Category.name)).all()


@router.post("/tickets", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(
    body: TicketCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.END_USER)),
):
    if db.get(Category, body.category_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown category")
    ticket = Ticket(
        title=body.title.strip(),
        description=body.description.strip(),
        category_id=body.category_id,
        priority=body.priority,
        status=Status.OPEN,
        created_by_id=user.id,
    )
    agent = pick_agent(db)
    ticket.assigned_to_id = agent.id if agent else None
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    status_filter: Status | None = Query(None, alias="status"),
    priority: Priority | None = None,
    category_id: int | None = None,
):
    """Role-scoped list: end users see their own tickets (US-04), agents see tickets
    assigned to them (US-06), administrators see everything."""
    q = select(Ticket)
    if user.role == Role.END_USER:
        q = q.where(Ticket.created_by_id == user.id)
    elif user.role == Role.AGENT:
        q = q.where(Ticket.assigned_to_id == user.id)
    if status_filter:
        q = q.where(Ticket.status == status_filter)
    if priority:
        q = q.where(Ticket.priority == priority)
    if category_id:
        q = q.where(Ticket.category_id == category_id)
    return db.scalars(q.order_by(Ticket.created_at.desc(), Ticket.id.desc())).all()


@router.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ticket = db.get(Ticket, ticket_id)
    # 404 rather than 403 so ticket IDs owned by others are not disclosed.
    if ticket is None or not can_view(user, ticket):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return ticket


@router.patch("/tickets/{ticket_id}/status", response_model=TicketOut)
def update_status(
    ticket_id: int,
    body: TicketStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.AGENT, Role.ADMIN)),
):
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or not can_view(user, ticket):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    if body.status not in STATUS_TRANSITIONS[ticket.status]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot change status from '{ticket.status.value}' to '{body.status.value}'",
        )
    ticket.status = body.status
    ticket.resolved_at = datetime.now(timezone.utc) if body.status == Status.RESOLVED else None
    db.commit()
    db.refresh(ticket)
    return ticket
