"""Acceptance tests for Sprint 1 user stories US-01..US-07."""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_helpdesk.db"
os.environ["SECRET_KEY"] = "test-secret"

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


# US-01 -----------------------------------------------------------------
def test_login_success_and_me(client):
    h = login(client, "user1@helpdesk.local")
    me = client.get("/api/auth/me", headers=h).json()
    assert me["email"] == "user1@helpdesk.local" and me["role"] == "end_user"


def test_login_wrong_password_rejected(client):
    r = client.post("/api/auth/login", data={"username": "user1@helpdesk.local", "password": "nope"})
    assert r.status_code == 401


def test_account_locks_after_repeated_failures(client):
    for _ in range(5):
        client.post("/api/auth/login", data={"username": "user2@helpdesk.local", "password": "bad"})
    r = client.post("/api/auth/login", data={"username": "user2@helpdesk.local", "password": DEMO_PASSWORD})
    assert r.status_code == 423


def test_protected_routes_require_token(client):
    assert client.get("/api/tickets").status_code == 401
    assert client.get("/api/tickets", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_register_creates_end_user(client):
    r = client.post("/api/auth/register", json={"email": "new@x.com", "full_name": "New", "password": "longenough"})
    assert r.status_code == 201 and r.json()["role"] == "end_user"
    assert client.post("/api/auth/register", json={"email": "NEW@x.com", "full_name": "N", "password": "longenough"}).status_code == 409


# US-02 -----------------------------------------------------------------
def test_non_admin_cannot_use_admin_features(client):
    for email in ("user1@helpdesk.local", "agent1@helpdesk.local"):
        assert client.get("/api/admin/users", headers=login(client, email)).status_code == 403


def test_admin_changes_role_and_deactivates(client):
    h = login(client, "admin@helpdesk.local")
    users = client.get("/api/admin/users", headers=h).json()
    target = next(u for u in users if u["email"] == "user2@helpdesk.local")
    r = client.patch(f"/api/admin/users/{target['id']}", json={"role": "agent"}, headers=h)
    assert r.json()["role"] == "agent"
    client.patch(f"/api/admin/users/{target['id']}", json={"is_active": False}, headers=h)
    r = client.post("/api/auth/login", data={"username": "user2@helpdesk.local", "password": DEMO_PASSWORD})
    assert r.status_code == 403


def test_admin_cannot_demote_self(client):
    h = login(client, "admin@helpdesk.local")
    me = client.get("/api/auth/me", headers=h).json()
    assert client.patch(f"/api/admin/users/{me['id']}", json={"role": "agent"}, headers=h).status_code == 400


# US-03 / US-05 ---------------------------------------------------------
def test_end_user_submits_ticket_with_category_priority_status(client):
    h = login(client, "user1@helpdesk.local")
    cat = client.get("/api/categories", headers=h).json()[0]
    r = client.post("/api/tickets", headers=h, json={
        "title": "Printer jam", "description": "The 3rd floor printer keeps jamming.", "category_id": cat["id"], "priority": "high"})
    assert r.status_code == 201
    t = r.json()
    assert t["status"] == "open" and t["priority"] == "high" and t["category"]["id"] == cat["id"]
    assert t["assigned_to"] is not None  # auto-routed to an agent


def test_ticket_validation(client):
    h = login(client, "user1@helpdesk.local")
    assert client.post("/api/tickets", headers=h, json={"title": "x", "description": "short", "category_id": 1}).status_code == 422
    assert client.post("/api/tickets", headers=h, json={"title": "Valid title", "description": "long enough text", "category_id": 999}).status_code == 422


def test_agents_cannot_submit_tickets(client):
    h = login(client, "agent1@helpdesk.local")
    assert client.post("/api/tickets", headers=h, json={"title": "abc", "description": "0123456789", "category_id": 1}).status_code == 403


def test_admin_manages_categories(client):
    h = login(client, "admin@helpdesk.local")
    r = client.post("/api/admin/categories", headers=h, json={"name": "Facilities"})
    assert r.status_code == 201
    assert client.delete(f"/api/admin/categories/{r.json()['id']}", headers=h).status_code == 204


# US-04 -----------------------------------------------------------------
def test_end_user_sees_only_own_tickets(client):
    h1 = login(client, "user1@helpdesk.local")
    mine = client.get("/api/tickets", headers=h1).json()
    assert mine and all(t["created_by"]["email"] == "user1@helpdesk.local" for t in mine)
    other = next(t for t in client.get("/api/tickets", headers=login(client, "user2@helpdesk.local")).json())
    assert client.get(f"/api/tickets/{other['id']}", headers=h1).status_code == 404


# US-06 -----------------------------------------------------------------
def test_agent_sees_only_assigned_tickets(client):
    h = login(client, "agent1@helpdesk.local")
    tickets = client.get("/api/tickets", headers=h).json()
    assert tickets and all(t["assigned_to"]["email"] == "agent1@helpdesk.local" for t in tickets)


# US-07 -----------------------------------------------------------------
def test_agent_updates_status_and_user_sees_it(client):
    ha = login(client, "agent1@helpdesk.local")
    t = next(t for t in client.get("/api/tickets", headers=ha).json() if t["status"] == "open")
    r = client.patch(f"/api/tickets/{t['id']}/status", headers=ha, json={"status": "in_progress"})
    assert r.status_code == 200 and r.json()["status"] == "in_progress"
    r = client.patch(f"/api/tickets/{t['id']}/status", headers=ha, json={"status": "resolved"})
    assert r.json()["resolved_at"] is not None
    hu = login(client, "user1@helpdesk.local")
    assert client.get(f"/api/tickets/{t['id']}", headers=hu).json()["status"] == "resolved"


def test_invalid_transition_rejected(client):
    ha = login(client, "agent2@helpdesk.local")
    t = next(t for t in client.get("/api/tickets", headers=ha).json() if t["status"] == "resolved")
    assert client.patch(f"/api/tickets/{t['id']}/status", headers=ha, json={"status": "open"}).status_code == 409


def test_agent_cannot_update_unassigned_ticket_and_user_cannot_update(client):
    ha2 = login(client, "agent2@helpdesk.local")
    a1_ticket = client.get("/api/tickets", headers=login(client, "agent1@helpdesk.local")).json()[0]
    assert client.patch(f"/api/tickets/{a1_ticket['id']}/status", headers=ha2, json={"status": "on_hold"}).status_code == 404
    hu = login(client, "user1@helpdesk.local")
    assert client.patch(f"/api/tickets/{a1_ticket['id']}/status", headers=hu, json={"status": "on_hold"}).status_code == 403
