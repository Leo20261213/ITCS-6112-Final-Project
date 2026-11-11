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


## Backend extensions for Sprints 2 and 3

The Python/FastAPI backend now includes additional API routes for the planned Sprint 2 and Sprint 3 workflows. Review and test these endpoints before marking stories complete in the sprint report.

### Sprint 2 — Ticket operations and communications

| Story | Backend capability | Endpoint |
|---|---|---|
| US-08 | Manager/admin assignment to an active agent | `PATCH /api/tickets/{ticket_id}/assignment` |
| US-09 | Ticket conversation messages | `POST/GET /api/tickets/{ticket_id}/comments` |
| US-10 | Edit an end-user's own open ticket | `PATCH /api/tickets/{ticket_id}` |
| US-11 | Close and reopen tickets | `POST /api/tickets/{ticket_id}/close`, `POST /api/tickets/{ticket_id}/reopen` |
| US-12 | View ticket action history | `GET /api/tickets/{ticket_id}/history` |
| US-13 | Upload/list/download ticket attachments | `/api/tickets/{ticket_id}/attachments` |
| US-14 | List notifications and mark them read | `GET /api/notifications`, `PATCH /api/notifications/{id}/read` |

Manager accounts must be granted by an administrator. Ticket attachments are limited by `MAX_UPLOAD_MB` (default 10 MB) and an extension allowlist. Production deployment should add malware scanning and storage outside the web root.

### Sprint 3 — AI assistance, chatbot, analytics

| Story | Backend capability | Endpoint |
|---|---|---|
| US-15 | Suggest ticket category | `POST /api/ai/tickets/{ticket_id}/classify` |
| US-16 | Suggest urgency/priority | Included in the classification response |
| US-17 | Summarize ticket and comments | `POST /api/ai/tickets/{ticket_id}/summary` |
| US-18 | Draft an agent response | `POST /api/ai/tickets/{ticket_id}/response-suggestion` |
| US-19 | Help-desk chatbot | `POST /api/ai/chat` |
| US-20 | Ticket volume/status/priority/resolution metrics | `GET /api/admin/analytics` |
| US-21 | Administrator AI settings | `GET/PUT /api/admin/ai-config` |

AI provider credentials are read only from environment variables. Configure `AI_API_KEY`, `AI_MODEL`, `AI_BASE_URL`, and `AI_ENABLED=true`. The API key is never returned by the configuration endpoint. Without a configured provider, endpoints use clearly labelled local demonstration fallbacks. Agents must review AI suggestions before applying or sending them.

### Environment configuration

The existing default remains SQLite for simple local development and automated tests. To use MySQL, install the driver from `requirements.txt` and set `DATABASE_URL`, for example:

```dotenv
DATABASE_URL=mysql+pymysql://helpdesk_user:your_password@localhost:3306/helpdesk_db?charset=utf8mb4
SECRET_KEY=replace-with-a-long-random-secret
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
UPLOAD_DIR=uploads
MAX_UPLOAD_MB=10
AI_ENABLED=false
AI_API_KEY=
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=
SEED_DEMO_DATA=1
```

Do not commit real credentials or `.env` files. `Base.metadata.create_all()` creates missing tables but does not migrate existing tables or alter an existing database's enum definitions. Use a reviewed migration (for example, Alembic) before upgrading an existing database, especially when adding the manager role and new tables.

### Verification status

These additions are committed to the feature branch for review. They must be installed, run, and tested against the team's target database and frontend before the corresponding user stories are reported as completed.
