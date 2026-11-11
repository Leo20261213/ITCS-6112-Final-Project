import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { api, fmtDate, labels } from "../api";
import { useAuth } from "../auth";
import { PriorityBadge, StatusBadge } from "../components/Badges";

// US-04 detail view, plus US-07 status updates for agents/admins.
export default function TicketDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const location = useLocation();
  const [ticket, setTicket] = useState(null);
  const [transitions, setTransitions] = useState({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(location.state?.created ? "Ticket submitted successfully." : "");
  const [nextStatus, setNextStatus] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api(`/tickets/${id}`).then(setTicket).catch((e) => setError(e.message));
    api("/meta").then((m) => setTransitions(m.status_transitions)).catch(() => {});
  }, [id]);

  const canUpdate = user.role === "agent" || user.role === "admin";
  const options = ticket ? transitions[ticket.status] || [] : [];

  const updateStatus = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const t = await api(`/tickets/${id}/status`, { method: "PATCH", body: { status: nextStatus } });
      setTicket(t);
      setNextStatus("");
      setNotice(`Status changed to “${labels[t.status]}”.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const back = { end_user: ["/tickets", "My tickets"], agent: ["/queue", "My queue"], admin: ["/admin", "Administration"] }[user.role];

  if (!ticket) {
    return (
      <div className="card empty">
        {error ? <><h2>{error}</h2><Link to={back[0]}>← Back to {back[1]}</Link></> : <p className="muted">Loading…</p>}
      </div>
    );
  }

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
      {notice && <div className="alert success">{notice}</div>}
      {error && <div className="alert error">{error}</div>}
      <div className="detail-grid">
        <section className="card">
          <h3>Description</h3>
          <p className="desc">{ticket.description}</p>
        </section>
        <aside className="card meta-list">
          <dl>
            <dt>Requester</dt><dd>{ticket.created_by.full_name}<br /><span className="muted small">{ticket.created_by.email}</span></dd>
            <dt>Assigned agent</dt><dd>{ticket.assigned_to?.full_name ?? <span className="muted">Awaiting assignment</span>}</dd>
            <dt>Submitted</dt><dd>{fmtDate(ticket.created_at)}</dd>
            <dt>Last updated</dt><dd>{fmtDate(ticket.updated_at)}</dd>
            {ticket.resolved_at && (<><dt>Resolved</dt><dd>{fmtDate(ticket.resolved_at)}</dd></>)}
          </dl>
          {canUpdate && (
            <form className="status-form" onSubmit={updateStatus}>
              <h3>Update status</h3>
              {options.length === 0 ? (
                <p className="muted small">No further status changes are available. Closing and reopening tickets arrive in Sprint 2.</p>
              ) : (
                <>
                  <select value={nextStatus} onChange={(e) => setNextStatus(e.target.value)} required aria-label="New status">
                    <option value="" disabled>Choose new status</option>
                    {options.map((s) => <option key={s} value={s}>{labels[s]}</option>)}
                  </select>
                  <button className="btn primary full" disabled={busy || !nextStatus}>{busy ? "Saving…" : "Save status"}</button>
                </>
              )}
            </form>
          )}
        </aside>
      </div>
    </>
  );
}
