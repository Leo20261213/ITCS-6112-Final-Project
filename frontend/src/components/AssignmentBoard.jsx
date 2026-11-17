import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import TicketTable from "./TicketTable";

/** US-08: every ticket, each agent's active workload, and an inline assignee picker.
 *  Used by managers and by administrators' "All tickets" tab. */
export default function AssignmentBoard() {
  const [agents, setAgents] = useState([]);
  const [reloadKey, setReloadKey] = useState(0);
  const [savingId, setSavingId] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const loadAgents = useCallback(() => api("/agents").then(setAgents).catch((e) => setError(e.message)), []);
  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  const assign = async (ticket, value) => {
    setSavingId(ticket.id);
    setError("");
    setNotice("");
    try {
      const t = await api(`/tickets/${ticket.id}/assignment`, {
        method: "PATCH",
        body: { agent_id: value ? Number(value) : null },
      });
      setNotice(t.assigned_to ? `Ticket #${t.id} assigned to ${t.assigned_to.full_name}.` : `Ticket #${t.id} is now unassigned.`);
      setReloadKey((k) => k + 1);
      loadAgents();
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingId(null);
    }
  };

  return (
    <>
      {agents.length > 0 && (
        <div className="workload" aria-label="Agent workload">
          {agents.map((a) => (
            <div key={a.id} className="workload-item">
              <span className="workload-count">{a.active_tickets}</span>
              <span>
                <b>{a.full_name}</b>
                <span className="muted small"> active ticket{a.active_tickets === 1 ? "" : "s"}</span>
              </span>
            </div>
          ))}
        </div>
      )}
      {notice && <div className="alert success">{notice}</div>}
      {error && <div className="alert error">{error}</div>}
      <TicketTable
        showRequester
        agents={agents}
        reloadKey={reloadKey}
        emptyText="No tickets match these filters."
        actionsHeader="Assigned to"
        actions={(t) => (
          <select
            className="compact"
            value={t.assigned_to?.id ?? ""}
            disabled={savingId === t.id || t.status === "closed"}
            title={t.status === "closed" ? "Reopen the ticket to reassign it" : undefined}
            onChange={(e) => assign(t, e.target.value)}
            aria-label={`Assign ticket ${t.id}`}
          >
            <option value="">Unassigned</option>
            {t.assigned_to && !agents.some((a) => a.id === t.assigned_to.id) && (
              <option value={t.assigned_to.id}>{t.assigned_to.full_name}</option>
            )}
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.full_name}</option>
            ))}
          </select>
        )}
      />
    </>
  );
}
