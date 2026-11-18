"""Seed demo accounts, categories, and sample tickets on first run."""
import os
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .help_content import ARTICLES
from .models import Category, EventKind, HelpArticle, Priority, Role, Status, Ticket, TicketEvent, TicketMessage, User
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
        _seed_help_articles(db)
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
    _seed_help_articles(db)
    if os.getenv("SEED_DEMO_HISTORY", "1") == "1":
        _seed_history(db, [a1, a2], [u1, u2], cats)


def _seed_help_articles(db: Session) -> None:
    """US-19: approved help content for the chatbot (added once, also to older databases)."""
    if db.scalar(select(HelpArticle).limit(1)) is not None:
        return
    for title, keywords, body in ARTICLES:
        db.add(HelpArticle(title=title, keywords=keywords, body=body))
    db.commit()


HISTORY = {
    "Hardware": [("Monitor flickers on the dock", "My second monitor flickers every few seconds when connected through the dock."),
                 ("Keyboard keys not responding", "Several keys on my laptop keyboard stopped working after a coffee spill."),
                 ("Printer on floor 3 jammed", "The floor 3 printer shows a paper jam that won't clear."),
                 ("Webcam not detected", "Teams says no camera is found on my laptop."),
                 ("Docking station not charging laptop", "The dock no longer charges my laptop, although screens work.")],
    "Software": [("Excel crashes when opening large files", "Excel freezes and crashes when I open the quarterly report."),
                 ("Request Visio license", "I need Visio for process diagrams for the audit project."),
                 ("Outlook search returns nothing", "Searching my mailbox returns no results since yesterday."),
                 ("Teams update failing", "Teams keeps showing an update error and won't start."),
                 ("Install Python for data analysis", "Please install Python and VS Code for my analytics work.")],
    "Network": [("Wi-Fi drops in the east wing", "Wi-Fi disconnects every few minutes in the east wing meeting rooms."),
                ("Slow internet at the branch office", "Pages take a very long time to load at the branch office."),
                ("Cannot reach shared drive", "The S: drive shows as disconnected and won't reconnect."),
                ("VPN connects but no internal sites load", "The VPN says connected, but intranet sites time out.")],
    "Account Access": [("Password expired while travelling", "My password expired and I can't sign in from the hotel."),
                       ("Need access to finance SharePoint", "I need read access to the Finance SharePoint site."),
                       ("MFA prompts not arriving", "I don't get MFA notifications on my new phone."),
                       ("Shared mailbox permission request", "Please give me send-as access to the support mailbox.")],
    "Other": [("Desk phone setup for new hire", "A new starter on Monday needs a desk phone configured."),
              ("Question about data retention policy", "How long are old project files kept on the shared drive?")],
}
RESOLUTION_HOURS = {Priority.CRITICAL: (1, 8), Priority.HIGH: (3, 26), Priority.MEDIUM: (6, 70), Priority.LOW: (20, 140)}


def _seed_history(db: Session, agents: list[User], users: list[User], cats: dict[str, Category]) -> None:
    """A month of realistic past tickets so the analytics dashboard (US-20) has data to show."""
    rng = random.Random(6112)
    now = datetime.now(timezone.utc)
    templates = [(cat, title, desc) for cat, rows in HISTORY.items() for title, desc in rows]
    for i in range(42):
        cat, title, desc = rng.choice(templates)
        prio = rng.choices(list(Priority), weights=[3, 5, 3, 1])[0]
        created = now - timedelta(days=rng.uniform(1.5, 34), hours=rng.uniform(0, 8))
        agent, requester = rng.choice(agents), rng.choice(users)
        lo, hi = RESOLUTION_HOURS[prio]
        resolved = created + timedelta(hours=rng.uniform(lo, hi))
        age_days = (now - created).total_seconds() / 86400
        if resolved < now and rng.random() < (0.9 if age_days > 4 else 0.5):
            st = Status.CLOSED if rng.random() < 0.6 else Status.RESOLVED
        else:
            st, resolved = rng.choice([Status.OPEN, Status.IN_PROGRESS, Status.IN_PROGRESS, Status.ON_HOLD]), None
        t = Ticket(title=title, description=desc, category_id=cats[cat].id, priority=prio, status=st,
                   created_by_id=requester.id, assigned_to_id=agent.id, created_at=created,
                   updated_at=resolved or created, resolved_at=resolved)
        db.add(t)
        db.flush()
        db.add(TicketEvent(ticket_id=t.id, actor_id=requester.id, kind=EventKind.CREATED, detail="Ticket submitted", created_at=created))
        db.add(TicketEvent(ticket_id=t.id, actor_id=None, kind=EventKind.ASSIGNED,
                           detail=f"Automatically assigned to {agent.full_name}", created_at=created))
        if resolved:
            db.add(TicketEvent(ticket_id=t.id, actor_id=agent.id, kind=EventKind.STATUS_CHANGED,
                               detail="Status changed from In progress to Resolved", created_at=resolved))
            if st == Status.CLOSED:
                db.add(TicketEvent(ticket_id=t.id, actor_id=agent.id, kind=EventKind.STATUS_CHANGED,
                                   detail="Ticket closed (was Resolved)", created_at=min(now, resolved + timedelta(days=2))))
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
