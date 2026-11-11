"""Seed demo accounts, categories, and sample tickets on first run."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Category, Priority, Role, Status, Ticket, User
from .security import hash_password

DEMO_PASSWORD = "Password123!"

DEMO_USERS = [
    ("admin@helpdesk.local", "Avery Admin", Role.ADMIN),
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


def seed(db: Session) -> None:
    if db.scalar(select(User).limit(1)) is not None:
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
    for title, desc, cat, prio, st, creator, agent in samples:
        db.add(Ticket(title=title, description=desc, category_id=cats[cat].id, priority=prio, status=st,
                      created_by_id=creator.id, assigned_to_id=agent.id))
    db.commit()
