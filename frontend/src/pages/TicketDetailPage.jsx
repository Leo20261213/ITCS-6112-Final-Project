import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { api, fmtDate, labels } from "../api";
import { useAuth } from "../auth";
import { PriorityBadge, StatusBadge } from "../components/Badges";
import TicketAttachments from "../components/TicketAttachments";
import TicketConversation from "../components/TicketConversation";
import TicketHistory from "../components/TicketHistory";

const BACK = {
  end_user: ["/tickets", "My tickets"],
  agent: ["/queue", "My queue"],
  manager: ["/manage", "Assignment board"],
  admin: ["/admin", "Administration"],
};

// Ticket workspace: details (US-04), status incl. close/reopen (US-07, US-11), assignment (US-08),
// conversation (US-09), editing (US-10), history (US-12), and attachments (US-13).
export default function TicketDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const location = useLocation();
  const [ticket, setTicket] = useState(null);
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(location.state?.created ? "Ticket submitted successfully." : "");
  const [historyKey, setHistoryKey] = useState(0);

  const bumpHistory = useCallback(() => setHistoryKey((k) => k + 1), []);

  useEffect(() => {
    setTicket(null);
    setError("");
    api(`/tickets/${id}`).then(setTicket).catch((e) => setError(e.message));
    api("/meta").then(setMeta).catch(() => {});
  }, [id]);

  const applyUpdate = (t, message) => {
    setTicket(t);
    setNotice(message);
    setError("");
    bumpHistory();
  };

  const back = BACK[user.role];

  if (!ticket) {
    return (
      <div className="card empty">
        {error ? <><h2>{error}</h2><Link to={back[0]}>← Back to {back[1]}</Link></> : <p className="muted">Loading…</p>}
      </div>
    );
  }

  const isStaff = ["agent", "manager", "admin"].includes(user.role);
  const canAssign = ["manager", "admin"].includes(user.role);

  return (
    <>
      <Link to={back[0]} className="back">← {back[1]}</Link>
      <div className="page-head">
        <div>
          <h1><span className="muted">#{ticket.id}</span> {ticket.title}</h1>
          <div className="badges">
            <StatusBadge value={ticket.status} />
            <PriorityBadge value={ticket.priority} />
            <span className="badge neutral">{ticket.category.name}</span>
          </div>
        </div>
      </div>
      {notice && <div className="alert success" role="status">{notice}</div>}
      {error && <div className="alert error">{error}</div>}
      <div className="detail-grid">
        <div className="stack">
          <DetailsCard ticket={ticket} user={user} meta={meta} onSaved={(t) => applyUpdate(t, "Ticket details updated.")} />
          <TicketConversation ticket={ticket} me={user} onActivity={bumpHistory} />
          <TicketAttachments ticket={ticket} rules={meta?.attachment_rules} onActivity={bumpHistory} />
          <TicketHistory ticketId={ticket.id} reloadKey={historyKey} />
        </div>
        <aside className="stack">
          <div className="card meta-list">
            <dl>
              <dt>Requester</dt><dd>{ticket.created_by.full_name}<br /><span className="muted small">{ticket.created_by.email}</span></dd>
              <dt>Assigned agent</dt><dd>{ticket.assigned_to?.full_name ?? <span className="muted">Awaiting assignment</span>}</dd>
              <dt>Submitted</dt><dd>{fmtDate(ticket.created_at)}</dd>
              <dt>Last updated</dt><dd>{fmtDate(ticket.updated_at)}</dd>
              {ticket.resolved_at && (<><dt>Resolved</dt><dd>{fmtDate(ticket.resolved_at)}</dd></>)}
            </dl>
            {isStaff && meta && (
              <StatusPanel ticket={ticket} transitions={meta.status_transitions} onChanged={applyUpdate} onError={setError} />
            )}
            {canAssign && <AssignPanel ticket={ticket} onChanged={applyUpdate} onError={setError} />}
          </div>
        </aside>
      </div>
    </>
  );
}

// US-10: the requester corrects details while the ticket is still open or on hold.
function DetailsCard({ ticket, user, meta, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [categories, setCategories] = useState([]);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const canEdit =
    user.role === "end_user" && ticket.created_by.id === user.id && meta?.editable_statuses.includes(ticket.status);

  useEffect(() => {
    if (!canEdit) setEditing(false);
  }, [canEdit]);

  const start = () => {
    setForm({ title: ticket.title, description: ticket.description, category_id: String(ticket.category.id), priority: ticket.priority });
    setError("");
    setEditing(true);
    if (!categories.length) api("/categories").then(setCategories).catch((e) => setError(e.message));
  };
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const save = async (e) => {
    e.preventDefault();
    const body = {};
    if (form.title.trim() !== ticket.title) body.title = form.title;
    if (form.description.trim() !== ticket.description) body.description = form.description;
    if (Number(form.category_id) !== ticket.category.id) body.category_id = Number(form.category_id);
    if (form.priority !== ticket.priority) body.priority = form.priority;
    if (!Object.keys(body).length) return setEditing(false);
    setBusy(true);
    setError("");
    try {
      const t = await api(`/tickets/${ticket.id}`, { method: "PATCH", body });
      setEditing(false);
      onSaved(t);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (editing && form) {
    return (
      <form className="card form edit-form" onSubmit={save}>
        <h3>Edit ticket details</h3>
        {error && <div className="alert error">{error}</div>}
        <label>
          Title
          <input value={form.title} onChange={set("title")} minLength={3} maxLength={200} required />
        </label>
        <div className="row">
          <label>
            Category
            <select value={form.category_id} onChange={set("category_id")} required>
              {categories.length === 0 && <option value={ticket.category.id}>{ticket.category.name}</option>}
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label>
            Priority
            <select value={form.priority} onChange={set("priority")}>
              {meta.priorities.map((p) => <option key={p} value={p}>{labels[p]}</option>)}
            </select>
          </label>
        </div>
        <label>
          Description
          <textarea rows={6} value={form.description} onChange={set("description")} minLength={10} maxLength={5000} required />
        </label>
        <div className="actions">
          <button type="button" className="btn ghost" onClick={() => setEditing(false)}>Cancel</button>
          <button className="btn primary" disabled={busy}>{busy ? "Saving…" : "Save changes"}</button>
        </div>
      </form>
    );
  }

  return (
    <section className="card">
      <div className="card-head">
        <h3>Description</h3>
        {canEdit && <button className="btn ghost small" onClick={start}>Edit details</button>}
      </div>
      <p className="desc">{ticket.description}</p>
      {user.role === "end_user" && meta && !canEdit && (
        <p className="muted small hint">Details can be edited while a ticket is Open or On hold. Use the conversation to add information.</p>
      )}
    </section>
  );
}

// US-07 status updates and US-11 close / reopen.
function StatusPanel({ ticket, transitions, onChanged, onError }) {
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const options = transitions[ticket.status] || [];
  const finished = ticket.status === "resolved" || ticket.status === "closed";
  const canReopen = finished && options.includes("open");
  const canClose = options.includes("closed");
  const regular = options.filter((s) => s !== "closed" && !(finished && s === "open"));

  const change = async (status) => {
    setBusy(true);
    try {
      const t = await api(`/tickets/${ticket.id}/status`, { method: "PATCH", body: { status } });
      setNext("");
      const msg = status === "closed" ? "Ticket closed." : canReopen && status === "open" ? "Ticket reopened." : `Status changed to “${labels[t.status]}”.`;
      onChanged(t, msg);
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="side-form">
      <h3>Status</h3>
      {regular.length > 0 && (
        <form
          className="side-form-row"
          onSubmit={(e) => {
            e.preventDefault();
            change(next);
          }}
        >
          <select value={next} onChange={(e) => setNext(e.target.value)} required aria-label="New status">
            <option value="" disabled>Change status…</option>
            {regular.map((s) => <option key={s} value={s}>{labels[s]}</option>)}
          </select>
          <button className="btn primary" disabled={busy || !next}>Save</button>
        </form>
      )}
      <div className="side-buttons">
        {canClose && (
          <button className="btn ghost full" disabled={busy} onClick={() => change("closed")}>Close ticket</button>
        )}
        {canReopen && (
          <button className="btn ghost full" disabled={busy} onClick={() => change("open")}>Reopen ticket</button>
        )}
      </div>
      {ticket.status === "closed" && <p className="muted small">Closed tickets are read-only until they are reopened.</p>}
    </div>
  );
}

// US-08: managers and administrators assign the ticket to an agent.
function AssignPanel({ ticket, onChanged, onError }) {
  const [agents, setAgents] = useState([]);
  const [choice, setChoice] = useState(String(ticket.assigned_to?.id ?? ""));
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/agents").then(setAgents).catch((e) => onError(e.message));
  }, [onError]);
  useEffect(() => setChoice(String(ticket.assigned_to?.id ?? "")), [ticket.assigned_to?.id]);

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const t = await api(`/tickets/${ticket.id}/assignment`, { method: "PATCH", body: { agent_id: choice ? Number(choice) : null } });
      onChanged(t, t.assigned_to ? `Assigned to ${t.assigned_to.full_name}.` : "Ticket unassigned.");
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const unchanged = choice === String(ticket.assigned_to?.id ?? "");
  const closed = ticket.status === "closed";

  return (
    <form className="side-form" onSubmit={save}>
      <h3>Assignment</h3>
      <div className="side-form-row">
        <select value={choice} onChange={(e) => setChoice(e.target.value)} disabled={closed} aria-label="Assign to agent">
          <option value="">Unassigned</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.full_name} ({a.active_tickets} active)
            </option>
          ))}
        </select>
        <button className="btn primary" disabled={busy || unchanged || closed}>Assign</button>
      </div>
      {closed && <p className="muted small">Reopen the ticket to reassign it.</p>}
    </form>
  );
}
