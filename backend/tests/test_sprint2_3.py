"""Acceptance tests for Sprint 2 and Sprint 3 API additions."""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_helpdesk.db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["AI_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app
from app.seed import DEMO_PASSWORD


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


def login(client, email):
    response = client.post(
        "/api/auth/login",
        data={"username": email, "password": DEMO_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def get_ticket_for(client, headers):
    response = client.get("/api/tickets", headers=headers)
    assert response.status_code == 200 and response.json()
    return response.json()[0]


def test_manager_assignment_endpoint_admin_can_assign(client):
    admin = login(client, "admin@helpdesk.local")
    ticket = get_ticket_for(client, login(client, "user1@helpdesk.local"))
    agent2 = next(
        u for u in client.get("/api/admin/users", headers=admin).json()
        if u["email"] == "agent2@helpdesk.local"
    )
    response = client.patch(
        f"/api/tickets/{ticket['id']}/assignment",
        headers=admin,
        json={"agent_id": agent2["id"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["assigned_to"]["email"] == "agent2@helpdesk.local"


def test_ticket_comments_and_history(client):
    user = login(client, "user1@helpdesk.local")
    ticket = get_ticket_for(client, user)
    response = client.post(
        f"/api/tickets/{ticket['id']}/comments",
        headers=user,
        json={"body": "I can provide another screenshot if needed."},
    )
    assert response.status_code == 201, response.text
    assert response.json()["body"].startswith("I can provide")
    comments = client.get(f"/api/tickets/{ticket['id']}/comments", headers=user)
    assert comments.status_code == 200 and len(comments.json()) == 1
    history = client.get(f"/api/tickets/{ticket['id']}/history", headers=user)
    assert history.status_code == 200
    assert any(item["action"] == "comment_added" for item in history.json())


def test_end_user_can_edit_only_own_open_ticket(client):
    user = login(client, "user1@helpdesk.local")
    ticket = next(t for t in client.get("/api/tickets", headers=user).json() if t["status"] == "open")
    categories = client.get("/api/categories", headers=user).json()
    response = client.patch(
        f"/api/tickets/{ticket['id']}",
        headers=user,
        json={
            "title": "Updated laptop support request",
            "description": "The laptop still fails to start after the initial troubleshooting.",
            "category_id": categories[0]["id"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Updated laptop support request"


def test_agent_can_close_and_reopen_ticket(client):
    agent = login(client, "agent1@helpdesk.local")
    ticket = next(t for t in client.get("/api/tickets", headers=agent).json() if t["status"] == "open")
    moved = client.patch(
        f"/api/tickets/{ticket['id']}/status",
        headers=agent,
        json={"status": "in_progress"},
    )
    assert moved.status_code == 200, moved.text
    closed = client.post(f"/api/tickets/{ticket['id']}/close", headers=agent)
    assert closed.status_code == 200 and closed.json()["status"] == "closed"
    reopened = client.post(f"/api/tickets/{ticket['id']}/reopen", headers=agent)
    assert reopened.status_code == 200 and reopened.json()["status"] == "in_progress"


def test_attachment_upload_list_and_download(client):
    user = login(client, "user1@helpdesk.local")
    ticket = get_ticket_for(client, user)
    uploaded = client.post(
        f"/api/tickets/{ticket['id']}/attachments",
        headers=user,
        files={"file": ("diagnostic.txt", b"sample diagnostic details", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment_id = uploaded.json()["id"]
    listed = client.get(f"/api/tickets/{ticket['id']}/attachments", headers=user)
    assert listed.status_code == 200 and listed.json()[0]["filename"] == "diagnostic.txt"
    downloaded = client.get(
        f"/api/tickets/{ticket['id']}/attachments/{attachment_id}/download",
        headers=user,
    )
    assert downloaded.status_code == 200
    assert downloaded.content == b"sample diagnostic details"


def test_notifications_are_private_and_mark_read(client):
    user = login(client, "user1@helpdesk.local")
    ticket = get_ticket_for(client, user)
    agent = login(client, "agent1@helpdesk.local")
    client.post(
        f"/api/tickets/{ticket['id']}/comments",
        headers=agent,
        json={"body": "We are investigating this issue."},
    )
    notifications = client.get("/api/notifications", headers=user)
    assert notifications.status_code == 200 and notifications.json()
    notification_id = notifications.json()[0]["id"]
    marked = client.patch(f"/api/notifications/{notification_id}/read", headers=user)
    assert marked.status_code == 200 and marked.json()["is_read"] is True


def test_ai_assistance_uses_safe_local_fallback_when_not_configured(client):
    agent = login(client, "agent1@helpdesk.local")
    ticket = get_ticket_for(client, agent)
    classified = client.post(f"/api/ai/tickets/{ticket['id']}/classify", headers=agent)
    assert classified.status_code == 200, classified.text
    assert classified.json()["requires_human_review"] is True
    summary = client.post(f"/api/ai/tickets/{ticket['id']}/summary", headers=agent)
    assert summary.status_code == 200 and summary.json()["summary"]
    suggestion = client.post(
        f"/api/ai/tickets/{ticket['id']}/response-suggestion",
        headers=agent,
    )
    assert suggestion.status_code == 200 and suggestion.json()["requires_agent_review"] is True
    chat = client.post("/api/ai/chat", headers=agent, json={"text": "How do I reset my password?"})
    assert chat.status_code == 200 and chat.json()["answer"]


def test_admin_analytics_and_ai_configuration(client):
    admin = login(client, "admin@helpdesk.local")
    analytics = client.get("/api/admin/analytics", headers=admin)
    assert analytics.status_code == 200
    assert "tickets_by_status" in analytics.json()
    config = client.put(
        "/api/admin/ai-config",
        headers=admin,
        json={
            "enabled": False,
            "provider": "openai_compatible",
            "model": "",
            "base_url": "https://api.openai.com/v1",
        },
    )
    assert config.status_code == 200, config.text
    assert config.json()["enabled"] is False
