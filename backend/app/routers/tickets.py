"""Core ticket lifecycle.

Sprint 1
US-03: As an end-user, I want to submit a support ticket so that I can request assistance.
US-04: As an end-user, I want to view my submitted tickets so that I can monitor their progress.
US-05: As a user, I want tickets to have categories, priorities, and statuses so that requests are organized.
US-06: As a support agent, I want to view tickets assigned to me so that I can manage my workload.
US-07: As a support agent, I want to update ticket statuses so that users can track progress.

Sprint 2
US-08: As a manager, I want to assign tickets to support agents so that requests reach the appropriate staff.
US-10: As an end user, I want to edit eligible ticket details so that I can correct information I submitted.
US-11: As a support agent, I want to close or reopen tickets so that resolution status is accurately maintained.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..access import OVERSIGHT_ROLES, STAFF_ROLES, get_visible_ticket
from ..activity import record
from ..ai import service as ai
from ..database import get_db
from ..models import Category, EventKind, Priority, Role, Status, Ticket, User
from ..schemas import (
    AgentWorkload,
    AssignmentUpdate,
    AttachmentRules,
    CategoryOut,
    MetaOut,
    TicketCreate,
    TicketOut,
    TicketStatusUpdate,
    TicketUpdate,
)
from ..security import get_current_user, require_roles
from .attachments import ALLOWED_EXTENSIONS, MAX_ATTACHMENT_BYTES, MAX_ATTACHMENTS_PER_TICKET

router = APIRouter(prefix="/api", tags=["tickets"])

# US-07 + US-11: valid status moves. Any non-closed ticket can be closed; resolved or
# closed tickets can be reopened, which returns them to Open.
STATUS_TRANSITIONS: dict[Status, list[Status]] = {
    Status.OPEN: [Status.IN_PROGRESS, Status.ON_HOLD, Status.RESOLVED, Status.CLOSED],
    Status.IN_PROGRESS: [Status.ON_HOLD, Status.RESOLVED, Status.CLOSED],
    Status.ON_HOLD: [Status.IN_PROGRESS, Status.RESOLVED, Status.CLOSED],
    Status.RESOLVED: [Status.OPEN, Status.CLOSED],
    Status.CLOSED: [Status.OPEN],
}
ACTIVE_STATUSES = (Status.OPEN, Status.IN_PROGRESS, Status.ON_HOLD)
# US-10: end users may correct a ticket until an agent has started on it or it is finished.
EDITABLE_STATUSES = (Status.OPEN, Status.ON_HOLD)

LABELS = {
    Status.OPEN: "Open",
    Status.IN_PROGRESS: "In progress",
    Status.ON_HOLD: "On hold",
    Status.RESOLVED: "Resolved",
    Status.CLOSED: "Closed",
}


def active_load():
    return (
        select(User, func.count(Ticket.id).label("load"))
        .outerjoin(Ticket, (Ticket.assigned_to_id == User.id) & Ticket.status.in_(ACTIVE_STATUSES))
        .where(User.role == Role.AGENT, User.is_active.is_(True))
        .group_by(User.id)
        .order_by("load", User.id)
    )


@router.get("/meta", response_model=MetaOut)
def meta(_: User = Depends(get_current_user)):
    return MetaOut(
        priorities=list(Priority),
        statuses=list(Status),
        roles=list(Role),
        status_transitions=STATUS_TRANSITIONS,
        editable_statuses=list(EDITABLE_STATUSES),
        attachment_rules=AttachmentRules(
            max_bytes=MAX_ATTACHMENT_BYTES,
            max_per_ticket=MAX_ATTACHMENTS_PER_TICKET,
            allowed_extensions=sorted(ALLOWED_EXTENSIONS),
        ),
    )


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Category).order_by(Category.name)).all()


@router.get("/agents", response_model=list[AgentWorkload])
def list_agents(db: Session = Depends(get_db), _: User = Depends(require_roles(*OVERSIGHT_ROLES))):
    """US-08: eligible agents and their current active workload, for assignment decisions."""
    return [
        AgentWorkload(id=u.id, full_name=u.full_name, email=u.email, active_tickets=load)
        for u, load in db.execute(active_load().order_by(None).order_by(User.full_name)).all()
    ]


@router.post("/tickets", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(
    body: TicketCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.END_USER)),
):
    chosen = None
    if body.category_id is not None:
        chosen = db.get(Category, body.category_id)
        if chosen is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown category")
    elif not ai.feature_enabled(ai.get_settings(db), "intake"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Choose a category for the ticket")
    provisional = chosen or db.scalars(select(Category).order_by(Category.id)).first()
    if provisional is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No ticket categories exist yet; ask an administrator to add one")
    ticket = Ticket(
        title=body.title.strip(),
        description=body.description.strip(),
        category=provisional,
        priority=body.priority,
        status=Status.OPEN,
        created_by=user,
    )
    db.add(ticket)
    db.flush()
    record(db, ticket, user, EventKind.CREATED, "Ticket submitted", notify=[])

    # Intake: AI categorizes the ticket (unless the requester chose a category) and routes it
    # to an agent. It falls back to built-in rules, so submission never fails because of AI.
    decision = ai.intake(db, user, ticket, chosen)
    ticket.category = decision.category
    ticket.assigned_to = decision.agent
    if decision.category_reason is not None:
        record(db, ticket, None, EventKind.EDITED,
               f"Categorized as {decision.category.name} by {decision.by}: {decision.category_reason}", notify=[])
    if decision.agent:
        record(
            db, ticket, None, EventKind.ASSIGNED,
            f"Automatically assigned to {decision.agent.full_name} by {decision.by}: {decision.routing_reason}",
            notify=[decision.agent],
            message=f"New ticket #{ticket.id} “{ticket.title}” was assigned to you",
        )
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
    assigned_to: int | None = None,
    unassigned: bool = False,
):
    """Role-scoped list: end users see their own tickets (US-04), agents see tickets
    assigned to them (US-06), managers and administrators see everything."""
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
    if assigned_to:
        q = q.where(Ticket.assigned_to_id == assigned_to)
    if unassigned:
        q = q.where(Ticket.assigned_to_id.is_(None))
    return db.scalars(q.order_by(Ticket.created_at.desc(), Ticket.id.desc())).all()


@router.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_visible_ticket(db, ticket_id, user)


@router.patch("/tickets/{ticket_id}", response_model=TicketOut)
def edit_ticket(
    ticket_id: int,
    body: TicketUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(Role.END_USER)),
):
    """US-10: the requester corrects title, description, category, or priority while the
    ticket is still editable. Restricted fields are refused by the schema."""
    ticket = get_visible_ticket(db, ticket_id, user)
    if ticket.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Tickets can only be edited while {' or '.join(LABELS[s] for s in EDITABLE_STATUSES)}",
        )
    if body.category_id is not None and db.get(Category, body.category_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown category")

    changes = {
        "title": body.title.strip() if body.title is not None else None,
        "description": body.description.strip() if body.description is not None else None,
        "category_id": body.category_id,
        "priority": body.priority,
    }
    changed = []
    names = {"title": "title", "description": "description", "category_id": "category", "priority": "priority"}
    for field, value in changes.items():
        if value is not None and getattr(ticket, field) != value:
            setattr(ticket, field, value)
            changed.append(names[field])
    if changed:
        db.flush()
        db.refresh(ticket)
        record(db, ticket, user, EventKind.EDITED, f"Requester updated the {', '.join(changed)}")
        db.commit()
        db.refresh(ticket)
    return ticket


@router.patch("/tickets/{ticket_id}/status", response_model=TicketOut)
def update_status(
    ticket_id: int,
    body: TicketStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*STAFF_ROLES)),
):
    """US-07 status updates, including US-11 close and reopen."""
    ticket = get_visible_ticket(db, ticket_id, user)
    old = ticket.status
    if body.status not in STATUS_TRANSITIONS[old]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot change status from '{old.value}' to '{body.status.value}'",
        )
    ticket.status = body.status
    if body.status == Status.RESOLVED:
        ticket.resolved_at = datetime.now(timezone.utc)
    elif body.status != Status.CLOSED:
        ticket.resolved_at = None  # reopened or back in progress

    if body.status == Status.CLOSED:
        detail = f"Ticket closed (was {LABELS[old]})"
    elif body.status == Status.OPEN:
        detail = f"Ticket reopened (was {LABELS[old]})"
    else:
        detail = f"Status changed from {LABELS[old]} to {LABELS[body.status]}"
    record(db, ticket, user, EventKind.STATUS_CHANGED, detail)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.patch("/tickets/{ticket_id}/assignment", response_model=TicketOut)
def assign_ticket(
    ticket_id: int,
    body: AssignmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*OVERSIGHT_ROLES)),
):
    """US-08: a manager (or administrator) assigns the ticket to an eligible agent."""
    ticket = get_visible_ticket(db, ticket_id, user)
    if ticket.status == Status.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Reopen the ticket before reassigning it")

    agent = None
    if body.agent_id is not None:
        agent = db.get(User, body.agent_id)
        if agent is None or agent.role != Role.AGENT or not agent.is_active:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Tickets can only be assigned to an active support agent")
    if ticket.assigned_to_id == (agent.id if agent else None):
        return ticket

    previous = ticket.assigned_to
    ticket.assigned_to = agent
    if agent:
        detail = f"Assigned to {agent.full_name}" + (f" (was {previous.full_name})" if previous else "")
    else:
        detail = f"Unassigned from {previous.full_name}"
    record(db, ticket, user, EventKind.ASSIGNED, detail, notify=[ticket.created_by, agent, previous])
    db.commit()
    db.refresh(ticket)
    return ticket
