import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtDate, labels } from "../api";
import { PriorityBadge, StatusBadge } from "./Badges";

/** Shared list with category/priority/status filters (US-05). The server scopes rows by role. */
export default function TicketTable({ showRequester = false, showAssignee = false, emptyText, reloadKey = 0 }) {
  const [tickets, setTickets] = useState(null);
  const [meta, setMeta] = useState(null);
  const [categories, setCategories] = useState([]);
  const [filters, setFilters] = useState({ status: "", priority: "", category_id: "" });
  const [error, setError] = useState("");

  useEffect(() => {
    api("/meta").then(setMeta).catch(() => {});
    api("/categories").then(setCategories).catch(() => {});
  }, []);

  useEffect(() => {
    const qs = new URLSearchParams(Object.entries(filters).filter(([, v]) => v)).toString();
    api(`/tickets${qs ? `?${qs}` : ""}`)
      .then((t) => {
        setTickets(t);
        setError("");
      })
      .catch((e) => setError(e.message));
  }, [filters, reloadKey]);

  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="card">
      <div className="filters">
        <select value={filters.status} onChange={set("status")} aria-label="Filter by status">
          <option value="">All statuses</option>
          {meta?.statuses.map((s) => <option key={s} value={s}>{labels[s]}</option>)}
        </select>
        <select value={filters.priority} onChange={set("priority")} aria-label="Filter by priority">
          <option value="">All priorities</option>
          {meta?.priorities.map((p) => <option key={p} value={p}>{labels[p]}</option>)}
        </select>
        <select value={filters.category_id} onChange={set("category_id")} aria-label="Filter by category">
          <option value="">All categories</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        {tickets && <span className="muted count">{tickets.length} ticket{tickets.length === 1 ? "" : "s"}</span>}
      </div>
      {error && <div className="alert error">{error}</div>}
      {!tickets ? (
        <p className="muted pad">Loading…</p>
      ) : tickets.length === 0 ? (
        <p className="muted pad">{emptyText}</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Title</th>
                <th>Category</th>
                <th>Priority</th>
                <th>Status</th>
                {showRequester && <th>Requester</th>}
                {showAssignee && <th>Assigned to</th>}
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {tickets.map((t) => (
                <tr key={t.id}>
                  <td className="muted">{t.id}</td>
                  <td><Link to={`/tickets/${t.id}`}>{t.title}</Link></td>
                  <td>{t.category.name}</td>
                  <td><PriorityBadge value={t.priority} /></td>
                  <td><StatusBadge value={t.status} /></td>
                  {showRequester && <td>{t.created_by.full_name}</td>}
                  {showAssignee && <td>{t.assigned_to?.full_name ?? <span className="muted">Unassigned</span>}</td>}
                  <td className="muted nowrap">{fmtDate(t.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
