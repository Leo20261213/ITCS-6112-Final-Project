import { useEffect, useState } from "react";
import { api, fmtDate } from "../api";

// US-12: chronological record of what has happened to a ticket.
export default function TicketHistory({ ticketId, reloadKey }) {
  const [events, setEvents] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/tickets/${ticketId}/history`).then(setEvents).catch((e) => setError(e.message));
  }, [ticketId, reloadKey]);

  return (
    <section className="card">
      <h3>History</h3>
      {error && <div className="alert error">{error}</div>}
      {!events ? (
        <p className="muted small">Loading…</p>
      ) : events.length === 0 ? (
        <p className="muted small">No recorded activity.</p>
      ) : (
        <ol className="timeline">
          {events.map((e) => (
            <li key={e.id} className={`ev ev-${e.kind}`}>
              <span className="ev-dot" aria-hidden />
              <div>
                <div>{e.detail}</div>
                <div className="muted small">
                  {e.actor ? e.actor.full_name : "System"} · <time dateTime={e.created_at}>{fmtDate(e.created_at)}</time>
                </div>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
