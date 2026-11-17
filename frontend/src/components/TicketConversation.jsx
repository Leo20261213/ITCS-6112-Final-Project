import { useCallback, useEffect, useRef, useState } from "react";
import { api, fmtDate, fmtRelative, labels } from "../api";

const POLL_MS = 15000;

// US-09: requester and support staff exchange messages on a ticket.
export default function TicketConversation({ ticket, me, onActivity }) {
  const [messages, setMessages] = useState(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef(null);
  const closed = ticket.status === "closed";

  const load = useCallback(
    () => api(`/tickets/${ticket.id}/messages`).then(setMessages).catch((e) => setError(e.message)),
    [ticket.id]
  );

  useEffect(() => {
    load();
    const id = setInterval(() => document.visibilityState === "visible" && load(), POLL_MS);
    return () => clearInterval(id);
  }, [load]);

  const count = messages?.length ?? 0;
  useEffect(() => {
    if (count) endRef.current?.scrollIntoView({ block: "nearest" });
  }, [count]);

  const send = async (e) => {
    e?.preventDefault();
    if (!draft.trim()) return;
    setBusy(true);
    setError("");
    try {
      const m = await api(`/tickets/${ticket.id}/messages`, { method: "POST", body: { body: draft } });
      setMessages((ms) => [...(ms || []), m]);
      setDraft("");
      onActivity?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card">
      <h3>Conversation</h3>
      {error && <div className="alert error">{error}</div>}
      {!messages ? (
        <p className="muted small">Loading…</p>
      ) : messages.length === 0 ? (
        <p className="muted small">
          No messages yet. {me.role === "end_user" ? "Add details or ask a question below." : "Ask the requester for anything you need below."}
        </p>
      ) : (
        <ol className="thread">
          {messages.map((m) => {
            const mine = m.author.id === me.id;
            const staff = m.author_role !== "end_user";
            return (
              <li key={m.id} className={`msg${mine ? " mine" : ""}${staff ? " staff" : ""}`}>
                <div className="msg-head">
                  <b>{mine ? "You" : m.author.full_name}</b>
                  <span className="muted small">{labels[m.author_role]}</span>
                  <time className="muted small" dateTime={m.created_at} title={fmtDate(m.created_at)}>{fmtRelative(m.created_at)}</time>
                </div>
                <p className="msg-body">{m.body}</p>
              </li>
            );
          })}
          <li ref={endRef} aria-hidden className="thread-end" />
        </ol>
      )}
      {closed ? (
        <p className="muted small closed-note">This ticket is closed. It must be reopened before anyone can reply.</p>
      ) : (
        <form className="composer" onSubmit={send}>
          <label className="sr-only" htmlFor="reply">Reply</label>
          <textarea
            id="reply"
            rows={3}
            maxLength={5000}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => (e.ctrlKey || e.metaKey) && e.key === "Enter" && send()}
            placeholder={me.role === "end_user" ? "Reply to support…" : `Reply to ${ticket.created_by.full_name}…`}
          />
          <div className="composer-actions">
            <span className="muted small">Ctrl + Enter to send</span>
            <button className="btn primary" disabled={busy || !draft.trim()}>{busy ? "Sending…" : "Send"}</button>
          </div>
        </form>
      )}
    </section>
  );
}
