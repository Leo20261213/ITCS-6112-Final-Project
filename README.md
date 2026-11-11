# ITCS-6112-Final-Project-
This is our collaboration for our final project in Software Systems Design and Implementation Capstone Course

## Help Desk System with AI Enhancements — Sprint 1 prototype

Sprint 1 objective: establish the secure foundation and core ticket lifecycle for end users and support agents.

| Story | Description | Where it lives |
|-------|-------------|----------------|
| US-01 | Secure login | `backend/app/routers/auth.py`, `backend/app/security.py` (PBKDF2 password hashing, expiring JWTs, lockout after 5 failed attempts) · `LoginPage.jsx`, `RegisterPage.jsx` |
| US-02 | Role-based access (admin) | `require_roles()` in `security.py`, `backend/app/routers/admin.py` · route guards in `App.jsx`, Users & roles tab in `AdminPage.jsx` |
| US-03 | End user submits a ticket | `POST /api/tickets` · `NewTicketPage.jsx` |
| US-04 | End user views own tickets | `GET /api/tickets` (scoped to the owner) · `MyTicketsPage.jsx`, `TicketDetailPage.jsx` |
| US-05 | Categories, priorities, statuses | `models.py` enums + `Category` table, admin category management, filters in `TicketTable.jsx` |
| US-06 | Agent views assigned tickets | `GET /api/tickets` (scoped to the assignee) · `AgentQueuePage.jsx` |
| US-07 | Agent updates ticket status | `PATCH /api/tickets/{id}/status` with validated transitions · status panel in `TicketDetailPage.jsx` |

Roles: **end user** (submits and tracks tickets), **support agent** (works their assigned queue), **administrator** (manages users, roles, categories; sees all tickets).

New tickets are routed automatically to the active agent with the fewest open tickets, so agents have a queue before manual manager assignment (US-08) arrives in Sprint 2. Closing and reopening tickets (US-11) are also Sprint 2, so Sprint 1 status changes are Open → In progress / On hold → Resolved.

### Running locally

Prerequisites: Python 3.11+ and Node 18+.

**Backend** (http://127.0.0.1:8000, interactive API docs at `/docs`):

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend** (http://localhost:5173, proxies `/api` to the backend):

```bash
cd frontend
npm install
npm run dev
```

The first time the backend starts, it creates `helpdesk.db` (SQLite) and loads demo data. Every demo account uses the password `Password123!`:

| Role | Email |
|------|-------|
| Administrator | admin@helpdesk.local |
| Support agent | agent1@helpdesk.local, agent2@helpdesk.local |
| End user | user1@helpdesk.local, user2@helpdesk.local |

To start from a clean database, delete `backend/helpdesk.db`. Set `SECRET_KEY` in the environment to keep users signed in across restarts; without it, a random key is generated on each start.

### Tests

```bash
cd backend
pytest
```

17 acceptance tests in `backend/tests/test_sprint1.py` cover US-01 through US-07, including the authorization cases: users can't see other users' tickets, agents can't update tickets they aren't assigned, and non-admins can't use admin endpoints.
