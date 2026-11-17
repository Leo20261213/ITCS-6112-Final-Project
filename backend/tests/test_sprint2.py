"""Acceptance tests for Sprint 2 user stories US-08..US-14.

Seeded tickets: #1 Laptop (user1 -> agent1, open), #2 VPN (user1 -> agent2, in progress),
#3 Acrobat (user2 -> agent1, on hold), #4 Locked out (user2 -> agent2, resolved).
"""
from conftest import login

MANAGER, ADMIN = "manager@helpdesk.local", "admin@helpdesk.local"
AGENT1, AGENT2 = "agent1@helpdesk.local", "agent2@helpdesk.local"
USER1, USER2 = "user1@helpdesk.local", "user2@helpdesk.local"

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def ticket_by_title(client, headers, prefix):
    return next(t for t in client.get("/api/tickets", headers=headers).json() if t["title"].startswith(prefix))


def agent_id(client, headers, email):
    return next(a["id"] for a in client.get("/api/agents", headers=headers).json() if a["email"] == email)


def notifications(client, email):
    return client.get("/api/notifications", headers=login(client, email)).json()


# US-08 Manager assigns tickets -----------------------------------------
def test_manager_sees_all_tickets_and_agent_workload(client):
    hm = login(client, MANAGER)
    assert len(client.get("/api/tickets", headers=hm).json()) == 4
    agents = client.get("/api/agents", headers=hm).json()
    assert {a["email"] for a in agents} == {AGENT1, AGENT2}
    assert all("active_tickets" in a for a in agents)


def test_assignment_moves_ticket_into_selected_agents_queue(client):
    hm = login(client, MANAGER)
    laptop = ticket_by_title(client, hm, "Laptop")
    r = client.patch(f"/api/tickets/{laptop['id']}/assignment", headers=hm, json={"agent_id": agent_id(client, hm, AGENT2)})
    assert r.status_code == 200 and r.json()["assigned_to"]["email"] == AGENT2

    queue2 = client.get("/api/tickets", headers=login(client, AGENT2)).json()
    assert laptop["id"] in [t["id"] for t in queue2]
    queue1 = client.get("/api/tickets", headers=login(client, AGENT1)).json()
    assert laptop["id"] not in [t["id"] for t in queue1]

    # The new agent and the requester are notified; the previous agent learns it moved.
    for email in (AGENT2, USER1, AGENT1):
        assert any("Assigned to Riley Agent" in n["message"] for n in notifications(client, email)["items"]), email


def test_only_managers_and_admins_assign_and_only_to_active_agents(client):
    hm = login(client, MANAGER)
    t = ticket_by_title(client, hm, "Laptop")
    a2 = agent_id(client, hm, AGENT2)
    for email in (AGENT1, USER1):
        assert client.patch(f"/api/tickets/{t['id']}/assignment", headers=login(client, email), json={"agent_id": a2}).status_code == 403
    assert client.patch(f"/api/tickets/{t['id']}/assignment", headers=login(client, ADMIN), json={"agent_id": a2}).status_code == 200

    user_id = client.get("/api/auth/me", headers=login(client, USER1)).json()["id"]
    assert client.patch(f"/api/tickets/{t['id']}/assignment", headers=hm, json={"agent_id": user_id}).status_code == 422
    assert client.patch(f"/api/tickets/9999/assignment", headers=hm, json={"agent_id": a2}).status_code == 404


def test_manager_cannot_use_admin_features(client):
    assert client.get("/api/admin/users", headers=login(client, MANAGER)).status_code == 403


# US-09 Messaging -------------------------------------------------------
def test_requester_and_agent_exchange_messages(client):
    hu, ha = login(client, USER1), login(client, AGENT1)
    t = ticket_by_title(client, hu, "Laptop")
    r = client.post(f"/api/tickets/{t['id']}/messages", headers=hu, json={"body": "It shows a blinking orange light."})
    assert r.status_code == 201
    msg = r.json()
    assert msg["author"]["email"] == USER1 and msg["author_role"] == "end_user" and msg["created_at"]

    client.post(f"/api/tickets/{t['id']}/messages", headers=ha, json={"body": "Please hold the power button for 30 seconds."})
    thread = client.get(f"/api/tickets/{t['id']}/messages", headers=hu).json()
    assert [m["author"]["email"] for m in thread] == [USER1, AGENT1]

    assert any("replied on ticket" in n["message"] for n in notifications(client, AGENT1)["items"])
    assert any("replied on ticket" in n["message"] for n in notifications(client, USER1)["items"])


def test_messages_are_private_to_authorized_participants(client):
    t = ticket_by_title(client, login(client, USER1), "Laptop")
    for email in (USER2, AGENT2):
        h = login(client, email)
        assert client.get(f"/api/tickets/{t['id']}/messages", headers=h).status_code == 404
        assert client.post(f"/api/tickets/{t['id']}/messages", headers=h, json={"body": "hi"}).status_code == 404
    assert client.post(f"/api/tickets/{t['id']}/messages", headers=login(client, USER1), json={"body": "   "}).status_code == 422


# US-10 Editing ---------------------------------------------------------
def test_owner_edits_eligible_ticket(client):
    hu = login(client, USER1)
    t = ticket_by_title(client, hu, "Laptop")
    cats = client.get("/api/categories", headers=hu).json()
    other = next(c for c in cats if c["id"] != t["category"]["id"])
    r = client.patch(f"/api/tickets/{t['id']}", headers=hu, json={
        "title": "Laptop will not power on at all", "category_id": other["id"], "priority": "critical"})
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Laptop will not power on at all" and body["category"]["id"] == other["id"]
    assert body["priority"] == "critical" and body["status"] == "open"
    history = client.get(f"/api/tickets/{t['id']}/history", headers=hu).json()
    assert history[-1]["kind"] == "edited" and "title" in history[-1]["detail"]


def test_restricted_fields_and_ineligible_tickets_are_unchanged(client):
    hu = login(client, USER1)
    laptop = ticket_by_title(client, hu, "Laptop")
    assert client.patch(f"/api/tickets/{laptop['id']}", headers=hu, json={"status": "closed"}).status_code == 422
    assert client.patch(f"/api/tickets/{laptop['id']}", headers=hu, json={"assigned_to_id": 1}).status_code == 422
    assert client.get(f"/api/tickets/{laptop['id']}", headers=hu).json()["status"] == "open"

    vpn = ticket_by_title(client, hu, "VPN")  # in progress, not editable
    assert client.patch(f"/api/tickets/{vpn['id']}", headers=hu, json={"title": "Changed title"}).status_code == 409
    assert client.get(f"/api/tickets/{vpn['id']}", headers=hu).json()["title"] == vpn["title"]

    # Someone else's ticket, and non-requesters, cannot edit.
    acrobat = ticket_by_title(client, login(client, USER2), "Need Adobe")
    assert client.patch(f"/api/tickets/{acrobat['id']}", headers=hu, json={"title": "Hijacked"}).status_code == 404
    assert client.patch(f"/api/tickets/{laptop['id']}", headers=login(client, AGENT1), json={"title": "Agent edit"}).status_code == 403


# US-11 Close / reopen --------------------------------------------------
def test_agent_closes_and_reopens_ticket(client):
    ha = login(client, AGENT2)
    t = ticket_by_title(client, ha, "Locked out")  # resolved
    r = client.patch(f"/api/tickets/{t['id']}/status", headers=ha, json={"status": "closed"})
    assert r.status_code == 200 and r.json()["status"] == "closed"
    assert r.json()["resolved_at"] is not None  # resolution time is kept when closing

    # A closed ticket accepts no new messages or files until it is reopened.
    hu = login(client, USER2)
    assert client.post(f"/api/tickets/{t['id']}/messages", headers=hu, json={"body": "One more thing"}).status_code == 409
    assert client.patch(f"/api/tickets/{t['id']}/status", headers=ha, json={"status": "in_progress"}).status_code == 409

    r = client.patch(f"/api/tickets/{t['id']}/status", headers=ha, json={"status": "open"})
    assert r.status_code == 200 and r.json()["status"] == "open" and r.json()["resolved_at"] is None
    kinds = [e["detail"] for e in client.get(f"/api/tickets/{t['id']}/history", headers=ha).json()]
    assert any(d.startswith("Ticket closed") for d in kinds) and any(d.startswith("Ticket reopened") for d in kinds)
    assert any("reopened" in n["message"] for n in notifications(client, USER2)["items"])


def test_active_ticket_can_be_closed_directly_and_users_cannot_close(client):
    ha = login(client, AGENT1)
    t = ticket_by_title(client, ha, "Laptop")
    assert client.patch(f"/api/tickets/{t['id']}/status", headers=login(client, USER1), json={"status": "closed"}).status_code == 403
    assert client.patch(f"/api/tickets/{t['id']}/status", headers=ha, json={"status": "closed"}).json()["status"] == "closed"


# US-12 History ---------------------------------------------------------
def test_history_is_chronological_and_covers_actions(client):
    hu = login(client, USER1)
    r = client.post("/api/tickets", headers=hu, json={
        "title": "Monitor flickers", "description": "External monitor flickers every few seconds.", "category_id": 1})
    tid = r.json()["id"]
    client.post(f"/api/tickets/{tid}/messages", headers=hu, json={"body": "It started after the update."})
    hm = login(client, MANAGER)
    current = r.json()["assigned_to"]["email"]
    other = AGENT1 if current == AGENT2 else AGENT2
    client.patch(f"/api/tickets/{tid}/assignment", headers=hm, json={"agent_id": agent_id(client, hm, other)})
    client.patch(f"/api/tickets/{tid}/status", headers=login(client, other), json={"status": "in_progress"})

    history = client.get(f"/api/tickets/{tid}/history", headers=hu).json()
    assert [e["kind"] for e in history] == ["created", "assigned", "message", "assigned", "status_changed"]
    stamps = [e["created_at"] for e in history]
    assert stamps == sorted(stamps)
    assert history[0]["actor"]["email"] == USER1 and history[1]["actor"] is None  # auto-routing is a system action

    assert client.get(f"/api/tickets/{tid}/history", headers=login(client, USER2)).status_code == 404


def test_seeded_history_and_conversation(client):
    hu = login(client, USER1)
    vpn = ticket_by_title(client, hu, "VPN")
    assert len(client.get(f"/api/tickets/{vpn['id']}/messages", headers=hu).json()) == 3
    assert client.get(f"/api/tickets/{vpn['id']}/history", headers=hu).json()[0]["kind"] == "created"


# US-13 Attachments -----------------------------------------------------
def test_upload_list_and_download_attachment(client):
    hu = login(client, USER1)
    t = ticket_by_title(client, hu, "Laptop")
    r = client.post(f"/api/tickets/{t['id']}/attachments", headers=hu, files={"file": ("screen.png", PNG, "image/png")})
    assert r.status_code == 201, r.text
    att = r.json()
    assert att["filename"] == "screen.png" and att["size"] == len(PNG) and att["content_type"] == "image/png"

    listed = client.get(f"/api/tickets/{t['id']}/attachments", headers=login(client, AGENT1)).json()
    assert [a["id"] for a in listed] == [att["id"]]
    d = client.get(f"/api/attachments/{att['id']}", headers=login(client, AGENT1))
    assert d.status_code == 200 and d.content == PNG
    assert "attachment" in d.headers["content-disposition"] and d.headers["x-content-type-options"] == "nosniff"

    assert any("attached screen.png" in n["message"] for n in notifications(client, AGENT1)["items"])


def test_attachment_rules_are_enforced(client):
    hu = login(client, USER1)
    t = ticket_by_title(client, hu, "Laptop")
    url = f"/api/tickets/{t['id']}/attachments"
    assert client.post(url, headers=hu, files={"file": ("tool.exe", b"MZ\x90\x00", "application/octet-stream")}).status_code == 415
    # Renamed executable: extension allowed but content is not an image.
    assert client.post(url, headers=hu, files={"file": ("photo.png", b"MZ\x90\x00binary", "image/png")}).status_code == 415
    assert client.post(url, headers=hu, files={"file": ("empty.txt", b"", "text/plain")}).status_code == 422
    big = b"a" * (5 * 1024 * 1024 + 1)
    assert client.post(url, headers=hu, files={"file": ("big.txt", big, "text/plain")}).status_code == 413
    assert client.post(url, headers=hu, files={"file": ("../../evil.txt", b"hello", "text/plain")}).json()["filename"] == "evil.txt"
    assert client.get(url, headers=hu).json()[0]["filename"] == "evil.txt"
    meta = client.get("/api/meta", headers=hu).json()["attachment_rules"]
    assert meta["max_bytes"] == 5 * 1024 * 1024 and "png" in meta["allowed_extensions"]


def test_attachments_require_ticket_access(client):
    hu = login(client, USER1)
    t = ticket_by_title(client, hu, "Laptop")
    att = client.post(f"/api/tickets/{t['id']}/attachments", headers=hu, files={"file": ("a.txt", b"log line", "text/plain")}).json()
    for email in (USER2, AGENT2):
        h = login(client, email)
        assert client.get(f"/api/attachments/{att['id']}", headers=h).status_code == 404
        assert client.post(f"/api/tickets/{t['id']}/attachments", headers=h, files={"file": ("b.txt", b"x", "text/plain")}).status_code == 404
    assert client.get(f"/api/attachments/{att['id']}").status_code == 401


# US-14 Notifications ---------------------------------------------------
def test_status_change_notifies_requester_not_actor(client):
    ha = login(client, AGENT1)
    t = ticket_by_title(client, ha, "Laptop")
    client.patch(f"/api/tickets/{t['id']}/status", headers=ha, json={"status": "in_progress"})
    user_n = notifications(client, USER1)
    assert user_n["unread"] >= 1
    assert any("Status changed from Open to In progress" in n["message"] and n["ticket_id"] == t["id"] for n in user_n["items"])
    assert not any("Status changed" in n["message"] for n in notifications(client, AGENT1)["items"])


def test_new_ticket_notifies_assigned_agent(client):
    hu = login(client, USER2)
    t = client.post("/api/tickets", headers=hu, json={
        "title": "Printer offline", "description": "The 2nd floor printer shows offline.", "category_id": 1}).json()
    agent_email = t["assigned_to"]["email"]
    assert any(n["ticket_id"] == t["id"] and "assigned to you" in n["message"] for n in notifications(client, agent_email)["items"])


def test_mark_notifications_read_and_privacy(client):
    ha = login(client, AGENT1)
    t = ticket_by_title(client, ha, "Laptop")
    client.patch(f"/api/tickets/{t['id']}/status", headers=ha, json={"status": "on_hold"})
    client.patch(f"/api/tickets/{t['id']}/status", headers=ha, json={"status": "in_progress"})
    hu = login(client, USER1)
    data = client.get("/api/notifications", headers=hu).json()
    assert data["unread"] >= 2
    first = data["items"][0]

    assert client.post(f"/api/notifications/{first['id']}/read", headers=login(client, USER2)).status_code == 404
    r = client.post(f"/api/notifications/{first['id']}/read", headers=hu)
    assert r.status_code == 200 and r.json()["is_read"] is True
    assert client.get("/api/notifications", headers=hu).json()["unread"] == data["unread"] - 1

    assert client.post("/api/notifications/read-all", headers=hu).status_code == 204
    assert client.get("/api/notifications", headers=hu).json()["unread"] == 0
