"""Shared test setup: an isolated SQLite database and upload folder, seeded with demo data."""
import os
import tempfile

# SQLite by default; set TEST_DATABASE_URL to run the suite against PostgreSQL, e.g.
# postgresql://helpdesk:helpdesk@localhost:5433/helpdesk_test (created by the db image).
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite:///./test_helpdesk.db")
os.environ["SECRET_KEY"] = "test-secret"
os.environ["SEED_DEMO_HISTORY"] = "0"  # keep the four known sample tickets
os.environ["AI_PROVIDER"] = "local"  # tests never call the real Claude API
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="helpdesk-test-uploads-")

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.seed import DEMO_PASSWORD


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:  # lifespan creates tables and seeds demo data
        yield c
    Base.metadata.drop_all(bind=engine)


def login(client, email, password=DEMO_PASSWORD):
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
