"""Database connection.

DATABASE_URL selects the database. The project's database is PostgreSQL, run from the
Docker image in /db (see docker-compose.yml), for example:
    postgresql://helpdesk:helpdesk@localhost:5433/helpdesk
Settings are read from the environment, and from backend/.env if present (environment wins).
Without DATABASE_URL the app falls back to a local SQLite file, which the tests also use.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def normalize_url(url: str) -> str:
    """Use the psycopg 3 driver for plain postgres:// and postgresql:// URLs."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


DATABASE_URL = normalize_url(os.getenv("DATABASE_URL", "sqlite:///./helpdesk.db"))
IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    pool_pre_ping=not IS_SQLITE,  # survive database restarts
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added in later increments. create_all() only creates missing tables, so existing
# databases get these through a plain ALTER TABLE on start-up.
_ADDED_COLUMNS = {
    "ai_settings": {"auto_triage": "BOOLEAN NOT NULL DEFAULT TRUE"},
}


def add_missing_columns() -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        if inspector.has_table("ai_settings"):
            # The default model changed from Opus to the lower-cost Haiku. Move settings that are
            # still on the old default and were never saved by an administrator.
            conn.execute(text(
                "UPDATE ai_settings SET model = 'claude-haiku-5-5' "
                "WHERE model = 'claude-opus-5-5' AND updated_by_id IS NULL"
            ))
