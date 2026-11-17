"""US-12 (ticket history) and US-14 (notifications) share one entry point.

Every ticket action calls `record()`, which appends a history event and notifies the
other people associated with the ticket. The person who acted is never notified about
their own action, and deactivated accounts are skipped.
"""
from collections.abc import Iterable

from sqlalchemy.orm import Session

from .models import EventKind, Notification, Ticket, TicketEvent, User


def participants(ticket: Ticket) -> list[User]:
    """The requester and the assigned agent: the people a ticket update concerns."""
    return [u for u in (ticket.created_by, ticket.assigned_to) if u is not None]


def record(
    db: Session,
    ticket: Ticket,
    actor: User | None,
    kind: EventKind,
    detail: str,
    notify: Iterable[User] | None = None,
    message: str | None = None,
) -> TicketEvent:
    """Add a history event for `ticket` and notify `notify` (default: its participants).

    `message` overrides the notification text; by default it is built from `detail`.
    The caller commits.
    """
    event = TicketEvent(ticket_id=ticket.id, actor_id=actor.id if actor else None, kind=kind, detail=detail)
    db.add(event)

    recipients = participants(ticket) if notify is None else list(notify)
    text = message or f"Ticket #{ticket.id} “{ticket.title}”: {detail}"
    seen: set[int] = set()
    for user in recipients:
        if user is None or user.id in seen or (actor and user.id == actor.id) or not user.is_active:
            continue
        seen.add(user.id)
        db.add(Notification(user_id=user.id, ticket_id=ticket.id, message=text[:500]))
    return event
