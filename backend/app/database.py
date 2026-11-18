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
from sqlalchemy import create_engine
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
