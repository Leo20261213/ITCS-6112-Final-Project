"""Seed demo accounts, categories, and sample tickets on first run."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Category, EventKind, Priority, Role, Status, Ticket, TicketEvent, TicketMessage, User
from .security import hash_password

DEMO_PASSWORD = "Password123!"

DEMO_USERS = [
    ("admin@helpdesk.local", "Avery Admin", Role.ADMIN),
    ("manager@helpdesk.local", "Morgan Manager", Role.MANAGER),
    ("agent1@helpdesk.local", "Sam Agent", Role.AGENT),
    ("agent2@helpdesk.local", "Riley Agent", Role.AGENT),
    ("user1@helpdesk.local", "Jordan User", Role.END_USER),
    ("user2@helpdesk.local", "Casey User", Role.END_USER),
]

DEMO_CATEGORIES = [
    ("Hardware", "Laptops, monitors, printers, peripherals"),
    ("Software", "Application installs, errors, and licensing"),
    ("Network", "Wi-Fi, VPN, and connectivity"),
    ("Account Access", "Passwords, MFA, and permissions"),
    ("Other", "Anything that does not fit another category"),
]

LABELS = {Status.OPEN: "Open", Status.IN_PROGRESS: "In progress", Status.ON_HOLD: "On hold", Status.RESOLVED: "Resolved"}


def seed(db: Session) -> None:
    if db.scalar(select(User).limit(1)) is not None:
        _add_missing_demo_users(db)
        return
    users = {}
    for email, name, role in DEMO_USERS:
        users[email] = User(email=email, full_name=name, role=role, password_hash=hash_password(DEMO_PASSWORD))
        db.add(users[email])
    cats = {}
    for name, desc in DEMO_CATEGORIES:
        cats[name] = Category(name=name, description=desc)
        db.add(cats[name])
    db.flush()

    a1, a2 = users["agent1@helpdesk.local"], users["agent2@helpdesk.local"]
    u1, u2 = users["user1@helpdesk.local"], users["user2@helpdesk.local"]
    samples = [
        ("Laptop will not power on", "My laptop does not turn on even after charging overnight.", "Hardware", Priority.HIGH, Status.OPEN, u1, a1),
        ("VPN disconnects every few minutes", "The VPN drops roughly every 5 minutes while working from home.", "Network", Priority.MEDIUM, Status.IN_PROGRESS, u1, a2),
        ("Need Adobe Acrobat license", "Please install Adobe Acrobat Pro for contract review work.", "Software", Priority.LOW, Status.ON_HOLD, u2, a1),
        ("Locked out of my account", "I entered the wrong password too many times and am now locked out.", "Account Access", Priority.CRITICAL, Status.RESOLVED, u2, a2),
    ]
    now = datetime.now(timezone.utc)
    for i, (title, desc, cat, prio, st, creator, agent) in enumerate(samples):
        created = now - timedelta(days=4 - i, hours=3)
        t = Ticket(title=title, description=desc, category_id=cats[cat].id, priority=prio, status=st,
                   created_by_id=creator.id, assigned_to_id=agent.id, created_at=created, updated_at=created,
                   resolved_at=created + timedelta(hours=5) if st == Status.RESOLVED else None)
        db.add(t)
        db.flush()
        db.add(TicketEvent(ticket_id=t.id, actor_id=creator.id, kind=EventKind.CREATED, detail="Ticket submitted", created_at=created))
        db.add(TicketEvent(ticket_id=t.id, actor_id=None, kind=EventKind.ASSIGNED,
                           detail=f"Automatically assigned to {agent.full_name}", created_at=created))
        if st == Status.OPEN:
            continue
        db.add(TicketEvent(ticket_id=t.id, actor_id=agent.id, kind=EventKind.STATUS_CHANGED,
                           detail=f"Status changed from Open to {LABELS[st]}", created_at=created + timedelta(hours=1)))

    # A short sample conversation (US-09) on the VPN ticket.
    vpn = db.scalar(select(Ticket).where(Ticket.title.like("VPN%")))
    convo = [
        (a2, "Hi Jordan, which VPN client version are you on? You can find it under Help > About."),
        (u1, "It says 5.2.1. It also seems worse on my home Wi-Fi than when I tether to my phone."),
        (a2, "Thanks, that helps. Version 5.2.1 has a known keep-alive bug. I'll push 5.3 to your laptop today."),
    ]
    for j, (author, body) in enumerate(convo):
        at = vpn.created_at + timedelta(hours=2 + j)
        db.add(TicketMessage(ticket_id=vpn.id, author_id=author.id, body=body, created_at=at))
        db.add(TicketEvent(ticket_id=vpn.id, actor_id=author.id, kind=EventKind.MESSAGE,
                           detail=f"{author.full_name} posted a message", created_at=at))
    db.commit()


def _add_missing_demo_users(db: Session) -> None:
    """Databases created before a demo role existed (e.g. Sprint 1 without a manager)
    get that demo account added, so every role can be tried out without a reset."""
    added = False
    for email, name, role in DEMO_USERS:
        if role != Role.MANAGER:
            continue
        if db.scalar(select(User).where(func.lower(User.email) == email)) is None:
            db.add(User(email=email, full_name=name, role=role, password_hash=hash_password(DEMO_PASSWORD)))
            added = True
    if added:
        db.commit()
