import { useCallback, useEffect, useRef, useState } from "react";
import { api, fmtDate, fmtRelative, labels } from "../api";
import { AiSource } from "./Ai";

const POLL_MS = 15000;

// US-09: requester and support staff exchange messages on a ticket.
// Staff also get an AI summary (US-17) and AI reply drafts they edit before sending (US-18).
export default function TicketConversation({ ticket, me, onActivity, features }) {
  const [messages, setMessages] = useState(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef(null);
  const closed = ticket.status === "closed";
  const isStaff = me.role !== "end_user";
  const canSummarize = isStaff && features?.summary;
  const canDraft = isStaff && features?.reply && !closed;
  const [summary, setSummary] = useState(null);
  const [summarizing, setSummarizing] = useState(false);
  const [aiDraft, setAiDraft] = useState(null);
  const [drafting, setDrafting] = useState(false);
  const [guidance, setGuidance] = useState("");

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
      setAiDraft(null);
      onActivity?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const summarize = async () => {
    setSummarizing(true);
    setError("");
    try {
      setSummary(await api(`/tickets/${ticket.id}/ai/summary`, { method: "POST" }));
    } catch (err) {
      setError(err.message);
    } finally {
      setSummarizing(false);
    }
  };

  const draftWithAi = async () => {
    if (draft.trim() && !aiDraft && !window.confirm("Replace your current reply with an AI draft?")) return;
    setDrafting(true);
    setError("");
    try {
      const r = await api(`/tickets/${ticket.id}/ai/reply`, { method: "POST", body: { instructions: guidance } });
      setDraft(r.reply);
      setAiDraft(r);
    } catch (err) {
      setError(err.message);
    } finally {
      setDrafting(false);
    }
  };

  return (
    <section className="card">
      <div className="card-head">
        <h3>Conversation</h3>
        {canSummarize && count > 0 && (
          <button className="btn ghost small" onClick={summarize} disabled={summarizing}>
            {summarizing ? "Summarizing…" : summary ? "Refresh summary" : "Summarize with AI"}
          </button>
        )}
      </div>
      {error && <div className="alert error">{error}</div>}
      {summary && (
        <div className="ai-box" role="region" aria-label="AI summary">
          <p className="ai-summary">{summary.summary}</p>
          {summary.key_points.length > 0 && (
            <ul className="key-points">
              {summary.key_points.map((k, i) => <li key={i}>{k}</li>)}
            </ul>
          )}
          <p className="small"><b>Suggested next step:</b> {summary.next_step}</p>
          <div className="ai-box-foot">
            <AiSource result={summary} review={`Based on ${summary.message_count} message${summary.message_count === 1 ? "" : "s"}; check the thread for details`} />
            <button className="link-btn small" onClick={() => setSummary(null)}>Hide</button>
          </div>
        </div>
      )}
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
          {aiDraft && (
            <div className="ai-draft-note">
              <AiSource result={aiDraft} review="Edit it as needed. Nothing is sent until you press Send" />
            </div>
          )}
          <textarea
            id="reply"
            rows={aiDraft ? 8 : 3}
            maxLength={5000}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => (e.ctrlKey || e.metaKey) && e.key === "Enter" && send()}
            placeholder={me.role === "end_user" ? "Reply to support…" : `Reply to ${ticket.created_by.full_name}…`}
          />
          <div className="composer-actions">
            {canDraft ? (
              <div className="ai-draft-controls">
                <input
                  value={guidance}
                  onChange={(e) => setGuidance(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault(); // never send the reply from this field
                      if (!drafting) draftWithAi();
                    }
                  }}
                  maxLength={300}
                  placeholder="Optional: what should the reply say?"
                  aria-label="Guidance for the AI draft"
                />
                <button type="button" className="btn ghost" onClick={draftWithAi} disabled={drafting}>
                  {drafting ? "Drafting…" : "Draft with AI"}
                </button>
              </div>
            ) : (
              <span className="muted small">Ctrl + Enter to send</span>
            )}
            <button className="btn primary" disabled={busy || !draft.trim()}>{busy ? "Sending…" : "Send"}</button>
          </div>
        </form>
      )}
    </section>
  );
}
