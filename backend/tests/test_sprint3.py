"""Acceptance tests for Sprint 3 user stories US-15..US-21.

The suite runs with AI_PROVIDER=local (built-in rules), so it never calls the real API.
The Claude path is exercised with a fake client that records each request and returns
canned structured output.
"""
import json
from types import SimpleNamespace

import anthropic
import pytest

from app.ai import claude
from conftest import login

ADMIN, MANAGER = "admin@helpdesk.local", "manager@helpdesk.local"
AGENT1, AGENT2 = "agent1@helpdesk.local", "agent2@helpdesk.local"
USER1, USER2 = "user1@helpdesk.local", "user2@helpdesk.local"


def ticket_by_title(client, headers, prefix):
    return next(t for t in client.get("/api/tickets", headers=headers).json() if t["title"].startswith(prefix))


def set_ai(client, **changes):
    r = client.put("/api/admin/ai-settings", headers=login(client, ADMIN), json=changes)
    assert r.status_code == 200, r.text
    return r.json()


class FakeClaude:
    """Stands in for anthropic.Anthropic: records requests, returns queued JSON payloads."""

    def __init__(self, *payloads, stop_reason="end_turn", error=None):
        self.payloads = list(payloads)
        self.stop_reason = stop_reason
        self.error = error
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        payload = self.payloads.pop(0)
        if callable(payload):  # built from the request, e.g. to pick a value from the schema's enum
            payload = payload(kwargs)
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=json.dumps(payload))],
        )


def schema_of(request):
    return request["output_config"]["format"]["schema"]


def route_to_first_agent(request):
    """An intake answer that keeps the requester's category and picks the first listed agent."""
    return {"assignee": schema_of(request)["properties"]["assignee"]["enum"][0], "routing_reason": "Least busy."}


@pytest.fixture()
def fake_claude(monkeypatch):
    def install(*payloads, **kw):
        fake = FakeClaude(*payloads, **kw)
        monkeypatch.setattr(claude, "get_client", lambda: fake)
        return fake
    return install


# US-15 / US-16 triage ----------------------------------------------------
def test_agent_gets_category_and_priority_suggestions(client):
    ha = login(client, AGENT1)
    t = ticket_by_title(client, ha, "Laptop")
    r = client.post(f"/api/tickets/{t['id']}/ai/triage", headers=ha)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "local" and body["model"] is None
    assert body["category"]["name"] == "Hardware" and 0 <= body["category"]["confidence"] <= 1
    assert body["priority"]["value"] in ("high", "critical") and body["priority"]["reason"]
    # Suggestions only: the ticket itself is unchanged.
    assert client.get(f"/api/tickets/{t['id']}", headers=ha).json()["priority"] == t["priority"]


def test_triage_flags_security_incident_as_critical(client):
    hu = login(client, USER1)
    t = client.post("/api/tickets", headers=hu, json={
        "title": "Suspicious email", "category_id": 5, "priority": "low",
        "description": "I clicked a link in a phishing email and now my account may be compromised."}).json()
    body = client.post(f"/api/tickets/{t['id']}/ai/triage", headers=login(client, t["assigned_to"]["email"])).json()
    assert body["priority"]["value"] == "critical" and body["priority"]["matches_current"] is False


def test_agent_applies_suggestion_with_history(client):
    ha = login(client, AGENT1)
    t = ticket_by_title(client, ha, "Need Adobe")
    cats = {c["name"]: c["id"] for c in client.get("/api/categories", headers=ha).json()}
    r = client.patch(f"/api/tickets/{t['id']}/classification", headers=ha,
                     json={"category_id": cats["Software"], "priority": "medium", "ai_assisted": True})
    assert r.status_code == 200 and r.json()["priority"] == "medium"
    last = client.get(f"/api/tickets/{t['id']}/history", headers=ha).json()[-1]
    assert "AI suggestion accepted" in last["detail"] and "priority from Low to Medium" in last["detail"]
    assert client.patch(f"/api/tickets/{t['id']}/classification", headers=login(client, USER2),
                        json={"priority": "high"}).status_code == 403


def test_ai_endpoints_are_staff_only_and_scoped(client):
    t = ticket_by_title(client, login(client, AGENT1), "Laptop")
    hu = login(client, USER1)
    for path in ("triage", "summary", "reply"):
        assert client.post(f"/api/tickets/{t['id']}/ai/{path}", headers=hu).status_code == 403
        assert client.post(f"/api/tickets/{t['id']}/ai/{path}", headers=login(client, AGENT2)).status_code == 404


# US-17 summary -----------------------------------------------------------
def test_summary_of_conversation(client):
    ha = login(client, AGENT2)
    vpn = ticket_by_title(client, ha, "VPN")
    r = client.post(f"/api/tickets/{vpn['id']}/ai/summary", headers=ha)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"] and body["key_points"] and body["next_step"] and body["message_count"] == 3


def test_summary_requires_conversation(client):
    ha = login(client, AGENT1)
    t = ticket_by_title(client, ha, "Laptop")
    assert client.post(f"/api/tickets/{t['id']}/ai/summary", headers=ha).status_code == 409


# US-18 reply draft -------------------------------------------------------
def test_reply_draft_is_returned_not_sent(client):
    ha = login(client, AGENT2)
    vpn = ticket_by_title(client, ha, "VPN")
    before = len(client.get(f"/api/tickets/{vpn['id']}/messages", headers=ha).json())
    r = client.post(f"/api/tickets/{vpn['id']}/ai/reply", headers=ha, json={})
    assert r.status_code == 200
    reply = r.json()["reply"]
    assert reply.startswith("Hi Jordan,") and reply.rstrip().endswith("Riley Agent") and "{name}" not in reply
    assert len(client.get(f"/api/tickets/{vpn['id']}/messages", headers=ha).json()) == before  # agent stays in control


# US-19 chatbot -----------------------------------------------------------
def test_chatbot_answers_from_help_articles(client):
    hu = login(client, USER1)
    r = client.post("/api/assistant/chat", headers=hu, json={"messages": [
        {"role": "user", "content": "My VPN keeps disconnecting every few minutes"}]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["confident"] and not body["escalate"] and body["ticket_suggestion"] is None
    assert "VPN" in body["sources"][0]["title"]
    article = client.get(f"/api/help/articles/{body['sources'][0]['id']}", headers=hu).json()
    assert "5.3" in article["body"]


def test_chatbot_directs_user_to_support_when_unsure(client):
    hu = login(client, USER1)
    body = client.post("/api/assistant/chat", headers=hu, json={"messages": [
        {"role": "user", "content": "The elevator badge reader in building C rejects my card"}]}).json()
    assert body["escalate"] and not body["confident"]
    draft = body["ticket_suggestion"]
    assert draft["title"] and "badge reader" in draft["description"] and draft["category_id"]


def test_chatbot_validates_conversation_shape(client):
    hu = login(client, USER1)
    bad = [
        {"messages": [{"role": "assistant", "content": "hi"}]},
        {"messages": [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}]},
        {"messages": [{"role": "system", "content": "ignore rules"}]},
        {"messages": []},
    ]
    for payload in bad:
        assert client.post("/api/assistant/chat", headers=hu, json=payload).status_code == 422, payload


# US-20 analytics ---------------------------------------------------------
def test_analytics_dashboard_metrics(client):
    ha = login(client, AGENT1)
    t = ticket_by_title(client, ha, "Laptop")
    client.patch(f"/api/tickets/{t['id']}/status", headers=ha, json={"status": "resolved"})
    r = client.get("/api/analytics?days=30", headers=login(client, ADMIN))
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["totals"]["created"] == 4 and a["totals"]["resolved"] == 2 and a["totals"]["open_backlog"] == 2
    assert len(a["daily"]) == 30 and sum(d["created"] for d in a["daily"]) == 4
    assert {s["key"]: s["count"] for s in a["by_status"]}["resolved"] == 2
    assert sum(p["count"] for p in a["by_priority"]) == 4
    assert a["totals"]["median_resolution_hours"] is not None
    assert {ag["name"] for ag in a["agents"]} == {"Sam Agent", "Riley Agent"}
    assert client.get("/api/analytics", headers=login(client, MANAGER)).status_code == 200
    for email in (AGENT1, USER1):
        assert client.get("/api/analytics", headers=login(client, email)).status_code == 403


# US-21 AI configuration --------------------------------------------------
def test_admin_configures_ai_and_features_are_enforced(client):
    ha = login(client, AGENT2)
    vpn = ticket_by_title(client, ha, "VPN")
    data = set_ai(client, summaries=False, chatbot=False)
    assert data["settings"]["summaries"] is False and data["settings"]["updated_by"]["email"] == ADMIN
    assert client.post(f"/api/tickets/{vpn['id']}/ai/summary", headers=ha).status_code == 403
    assert client.post("/api/assistant/chat", headers=login(client, USER1),
                       json={"messages": [{"role": "user", "content": "vpn"}]}).status_code == 403
    flags = client.get("/api/ai/features", headers=ha).json()
    assert flags["summary"] is False and flags["reply"] is True

    set_ai(client, enabled=False)
    assert client.post(f"/api/tickets/{vpn['id']}/ai/reply", headers=ha, json={}).status_code == 403
    assert client.get("/api/ai/features", headers=ha).json()["reply"] is False

    # Turning one of the two triage features off removes it from the result.
    set_ai(client, enabled=True, priority_suggestions=False)
    body = client.post(f"/api/tickets/{vpn['id']}/ai/triage", headers=ha).json()
    assert body["category"] and body["priority"] is None


def test_ai_settings_validation_and_admin_only(client):
    h = login(client, ADMIN)
    assert client.put("/api/admin/ai-settings", headers=h, json={"model": "gpt-4"}).status_code == 422
    assert client.put("/api/admin/ai-settings", headers=h, json={"provider": "other"}).status_code == 422
    assert client.put("/api/admin/ai-settings", headers=h, json={"temperature": 2}).status_code == 422
    for email in (MANAGER, AGENT1, USER1):
        assert client.get("/api/admin/ai-settings", headers=login(client, email)).status_code == 403


def test_ai_usage_is_logged_without_content(client):
    ha = login(client, AGENT2)
    vpn = ticket_by_title(client, ha, "VPN")
    client.post(f"/api/tickets/{vpn['id']}/ai/summary", headers=ha)
    report = client.get("/api/admin/ai-usage", headers=login(client, ADMIN)).json()
    item = report["items"][0]
    assert item["feature"] == "summary" and item["ticket_id"] == vpn["id"] and item["source"] == "local"
    assert report["totals"]["all"] >= 1 and set(item) >= {"outcome", "latency_ms", "user"}


# Claude provider (fake client) ------------------------------------------
def test_claude_triage_request_shape_and_redaction(client, fake_claude):
    set_ai(client, provider="claude", model="claude-opus-5-5")
    fake = fake_claude(route_to_first_agent, {
        "category": "Hardware", "category_confidence": 0.92, "category_reason": "Device will not power on.",
        "priority": "high", "urgency_signals": ["does not turn on"], "priority_confidence": 0.8,
        "priority_reason": "The requester cannot work.",
    })
    hu = login(client, USER1)
    t = client.post("/api/tickets", headers=hu, json={
        "title": "Dock problem", "category_id": 1,
        "description": "Jordan here, reach me at jordan.user@example.com or 704-555-0199. The dock does not turn on."}).json()
    agent = login(client, t["assigned_to"]["email"])
    body = client.post(f"/api/tickets/{t['id']}/ai/triage", headers=agent).json()
    assert body["source"] == "claude" and body["model"] == "claude-opus-5-5"
    assert body["category"]["name"] == "Hardware" and body["priority"]["value"] == "high"

    req = fake.requests[1]  # requests[0] was intake, when the ticket was submitted
    assert req["model"] == "claude-opus-5-5"
    assert req["output_config"]["effort"] == "low" and req["output_config"]["format"]["type"] == "json_schema"
    assert req["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in req["betas"]
    assert "thinking" not in req and "temperature" not in req
    sent = req["messages"][0]["content"]
    assert "jordan.user@example.com" not in sent and "704-555-0199" not in sent and "Jordan" not in sent
    assert "[email]" in sent and "[phone]" in sent


def test_claude_out_of_range_answer_is_rejected(client, fake_claude):
    set_ai(client, provider="auto")
    fake_claude({"category": "Plumbing", "category_confidence": 1, "category_reason": "x", "priority": "high",
                 "urgency_signals": [], "priority_confidence": 1, "priority_reason": "x"})
    ha = login(client, AGENT1)
    t = ticket_by_title(client, ha, "Laptop")
    body = client.post(f"/api/tickets/{t['id']}/ai/triage", headers=ha).json()
    assert body["source"] == "local" and "outside the allowed options" in body["notice"]


def test_auto_mode_falls_back_and_strict_mode_reports(client, fake_claude):
    fake_claude(error=anthropic.APIConnectionError(request=None))
    ha = login(client, AGENT2)
    vpn = ticket_by_title(client, ha, "VPN")
    set_ai(client, provider="auto")
    body = client.post(f"/api/tickets/{vpn['id']}/ai/summary", headers=ha).json()
    assert body["source"] == "local" and "Could not reach Claude" in body["notice"]

    set_ai(client, provider="claude")
    r = client.post(f"/api/tickets/{vpn['id']}/ai/summary", headers=ha)
    assert r.status_code == 503 and "Could not reach Claude" in r.json()["detail"]
    outcomes = [i["outcome"] for i in client.get("/api/admin/ai-usage", headers=login(client, ADMIN)).json()["items"][:2]]
    assert outcomes == ["error", "fallback"]


def test_claude_refusal_is_not_shown_as_an_answer(client, fake_claude):
    set_ai(client, provider="claude")
    fake_claude({"reply": "should not be used"}, stop_reason="refusal")
    ha = login(client, AGENT2)
    vpn = ticket_by_title(client, ha, "VPN")
    r = client.post(f"/api/tickets/{vpn['id']}/ai/reply", headers=ha, json={})
    assert r.status_code == 503 and "declined" in r.json()["detail"]


def test_claude_reply_fills_placeholders_and_uses_guidance(client, fake_claude):
    set_ai(client, provider="claude", model="claude-haiku-5-5", reply_guidance="Always mention our self-service portal.")
    fake = fake_claude({"reply": "Hi {name},\n\nPlease update to VPN 5.3.\n\nThanks,\n{agent}"})
    ha = login(client, AGENT2)
    vpn = ticket_by_title(client, ha, "VPN")
    body = client.post(f"/api/tickets/{vpn['id']}/ai/reply", headers=ha, json={"instructions": "be brief"}).json()
    assert body["reply"] == "Hi Jordan,\n\nPlease update to VPN 5.3.\n\nThanks,\nRiley Agent"
    req = fake.requests[0]
    assert req["model"] == "claude-haiku-5-5" and "fallbacks" not in req  # Haiku has no server-side fallback
    assert "self-service portal" in req["system"] and "<agent_request>be brief</agent_request>" in req["messages"][0]["content"]


def test_claude_chatbot_drops_unknown_sources(client, fake_claude):
    set_ai(client, provider="claude")
    fake = fake_claude({"answer": "Update the VPN client.", "confident": True, "article_ids": [999],
                        "escalate": False, "ticket_title": ""})
    body = client.post("/api/assistant/chat", headers=login(client, USER1), json={"messages": [
        {"role": "user", "content": "vpn drops"}]}).json()
    # Claude cited an article that doesn't exist, so the answer is not presented as confident.
    assert body["source"] == "claude" and body["sources"] == [] and body["confident"] is False
    system = fake.requests[0]["system"][0]
    assert system["cache_control"] == {"type": "ephemeral"} and "<approved_articles>" in system["text"]


def test_ai_settings_survive_concurrent_first_reads(client):
    """Regression: two requests creating the settings row at once caused a UNIQUE-constraint 500."""
    import threading

    from app.database import SessionLocal
    from app.models import AiSettings

    with SessionLocal() as db:  # as in a database created before the settings row existed
        db.query(AiSettings).delete()
        db.commit()
    h = login(client, ADMIN)
    codes = []
    threads = [threading.Thread(target=lambda: codes.append(client.get("/api/admin/ai-settings", headers=h).status_code))
               for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert codes == [200] * 8


# Automatic intake: categorization and routing of new tickets ------------------------
def history_of(client, headers, ticket_id):
    return [e["detail"] for e in client.get(f"/api/tickets/{ticket_id}/history", headers=headers).json()]


def test_new_ticket_is_categorized_and_routed_automatically(client):
    hu = login(client, USER1)
    r = client.post("/api/tickets", headers=hu, json={
        "title": "VPN keeps disconnecting", "description": "My VPN connection drops every ten minutes at home."})
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["category"]["name"] == "Network" and t["assigned_to"] is not None
    events = history_of(client, hu, t["id"])
    assert any(e.startswith("Categorized as Network by built-in rules") for e in events)
    assert any(e.startswith(f"Automatically assigned to {t['assigned_to']['full_name']} by built-in rules") for e in events)
    # The requester's own choice of category is kept.
    cats = {c["name"]: c["id"] for c in client.get("/api/categories", headers=hu).json()}
    t2 = client.post("/api/tickets", headers=hu, json={
        "title": "VPN question", "description": "Which VPN server should I use abroad?", "category_id": cats["Other"]}).json()
    assert t2["category"]["name"] == "Other"
    assert not any(e.startswith("Categorized as") for e in history_of(client, hu, t2["id"]))


def test_rules_route_to_least_busy_agent(client):
    from app.ai.service import agent_roster
    from app.database import SessionLocal

    with SessionLocal() as db:
        roster = agent_roster(db)
    least = min(a.load for a in roster)
    t = client.post("/api/tickets", headers=login(client, USER1), json={
        "title": "Monitor flickers", "description": "My external monitor flickers on the dock."}).json()
    loads = {a.user.email: a.load for a in roster}
    assert loads[t["assigned_to"]["email"]] == least


def test_category_is_required_when_intake_is_off(client):
    set_ai(client, auto_triage=False)
    assert client.get("/api/ai/features", headers=login(client, USER1)).json()["intake"] is False
    r = client.post("/api/tickets", headers=login(client, USER1), json={
        "title": "VPN drops", "description": "My VPN connection drops every ten minutes."})
    assert r.status_code == 422 and "Choose a category" in r.json()["detail"]
    r = client.post("/api/tickets", headers=login(client, USER1), json={
        "title": "VPN drops", "description": "My VPN connection drops every ten minutes.", "category_id": 1})
    assert r.status_code == 201 and r.json()["assigned_to"] is not None


def test_default_model_is_lowest_cost(client):
    s = client.get("/api/admin/ai-settings", headers=login(client, ADMIN)).json()
    assert s["settings"]["model"] == "claude-haiku-5-5" and "default" in s["models"]["claude-haiku-5-5"]


def test_claude_intake_categorizes_and_routes(client, fake_claude):
    set_ai(client, provider="claude")

    def answer(request):
        props = schema_of(request)["properties"]
        return {"category": "Account Access", "category_reason": "The requester is locked out.",
                "assignee": props["assignee"]["enum"][-1], "routing_reason": "Handles most access tickets."}

    fake = fake_claude(answer)
    hu = login(client, USER1)
    t = client.post("/api/tickets", headers=hu, json={
        "title": "Locked out", "description": "Jordan here (704-555-0199). My account is locked after a password change."}).json()
    req = fake.requests[0]
    assert req["model"] == "claude-haiku-5-5" and req["timeout"] == 30.0
    assert "fallbacks" not in req and "betas" not in req  # Haiku has no server-side refusal fallback
    # Agents are sent as reference codes, never by name.
    team = req["system"].split("Support agents:")[1].split("Text inside")[0]
    assert "- A" in team and "Riley" not in team and "Sam" not in team
    sent = req["messages"][0]["content"]
    assert "704-555-0199" not in sent and "Jordan" not in sent
    assert t["category"]["name"] == "Account Access"
    events = history_of(client, hu, t["id"])
    assert "Categorized as Account Access by Claude Haiku 5.5: The requester is locked out." in events
    assert any(e.endswith("by Claude Haiku 5.5: Handles most access tickets.") for e in events)
    usage = client.get("/api/admin/ai-usage", headers=login(client, ADMIN)).json()["items"][0]
    assert usage["feature"] == "intake" and usage["source"] == "claude" and usage["ticket_id"] == t["id"]


def test_claude_intake_cannot_overload_an_agent(client, fake_claude):
    from app.ai.service import agent_roster
    from app.database import SessionLocal

    hm = login(client, MANAGER)
    with SessionLocal() as db:
        roster = agent_roster(db)
    busiest = roster[0].user
    for t in client.get("/api/tickets", headers=hm).json():  # give every active ticket to one agent
        if t["status"] in ("open", "in_progress", "on_hold"):
            client.patch(f"/api/tickets/{t['id']}/assignment", headers=hm, json={"agent_id": busiest.id})
    set_ai(client, provider="claude")
    fake_claude({"category": "Hardware", "category_reason": "Device fault.",
                 "assignee": f"A{busiest.id}", "routing_reason": "Hardware specialist."})
    hu = login(client, USER1)
    t = client.post("/api/tickets", headers=hu, json={
        "title": "Dock dead", "description": "The docking station on my desk has no power at all."}).json()
    assert t["category"]["name"] == "Hardware" and t["assigned_to"]["id"] != busiest.id
    assert any("too many active tickets" in e for e in history_of(client, hu, t["id"]))


def test_intake_never_blocks_submission(client, fake_claude):
    set_ai(client, provider="claude")  # Claude only: intake still falls back, so the ticket is created
    fake_claude(error=anthropic.APIConnectionError(request=None))
    r = client.post("/api/tickets", headers=login(client, USER1), json={
        "title": "Printer offline", "description": "The 2nd floor printer shows offline for everyone."})
    assert r.status_code == 201 and r.json()["assigned_to"] is not None
    set_ai(client, provider="auto")
    fake_claude({"category": "Plumbing", "category_reason": "x", "assignee": "A1", "routing_reason": "x"})
    r = client.post("/api/tickets", headers=login(client, USER1), json={
        "title": "Printer offline", "description": "The 2nd floor printer shows offline for everyone."})
    assert r.status_code == 201 and r.json()["category"]["name"] == "Hardware"
