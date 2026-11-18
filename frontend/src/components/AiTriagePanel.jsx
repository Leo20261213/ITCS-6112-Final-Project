import { useState } from "react";
import { api, labels } from "../api";
import { AiSource, pct } from "./Ai";

// US-15 (category) and US-16 (urgency / priority): suggestions the agent reviews and applies.
export default function AiTriagePanel({ ticket, features, onChanged, onError }) {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [applying, setApplying] = useState(null);

  if (!features?.category && !features?.priority) return null;
  const closed = ticket.status === "closed";

  const suggest = async () => {
    setBusy(true);
    try {
      setResult(await api(`/tickets/${ticket.id}/ai/triage`, { method: "POST" }));
    } catch (e) {
      onError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const apply = async (what) => {
    setApplying(what);
    const body = { ai_assisted: true };
    if (what === "category" || what === "both") body.category_id = result.category.id;
    if (what === "priority" || what === "both") body.priority = result.priority.value;
    try {
      const t = await api(`/tickets/${ticket.id}/classification`, { method: "PATCH", body });
      setResult((r) => ({
        ...r,
        category: r.category && { ...r.category, matches_current: r.category.id === t.category.id },
        priority: r.priority && { ...r.priority, matches_current: r.priority.value === t.priority },
      }));
      onChanged(t, "AI suggestion applied.");
    } catch (e) {
      onError(e.message);
    } finally {
      setApplying(null);
    }
  };

  const c = result?.category;
  const p = result?.priority;
  const both = c && p && !c.matches_current && !p.matches_current;

  return (
    <div className="side-form">
      <h3>AI triage</h3>
      {!result ? (
        <>
          <p className="muted small">Get a suggested {features.category ? "category" : ""}{features.category && features.priority ? " and " : ""}{features.priority ? "priority" : ""} based on the ticket text.</p>
          <button className="btn ghost full" onClick={suggest} disabled={busy}>
            {busy ? "Analyzing…" : "Suggest with AI"}
          </button>
        </>
      ) : (
        <div className="suggestions">
          {c && (
            <div className="suggestion">
              <div className="suggestion-head">
                <span className="muted small">Category</span>
                <span className="muted small">{pct(c.confidence)} confidence</span>
              </div>
              <b>{c.name}</b>
              <p className="small">{c.reason}</p>
              {c.matches_current ? (
                <span className="small ok-text">✓ Matches the current category</span>
              ) : (
                <button className="btn ghost small" disabled={closed || applying} onClick={() => apply("category")}>
                  Apply category
                </button>
              )}
            </div>
          )}
          {p && (
            <div className="suggestion">
              <div className="suggestion-head">
                <span className="muted small">Priority</span>
                <span className="muted small">{pct(p.confidence)} confidence</span>
              </div>
              <b>{labels[p.value]}</b>
              <p className="small">{p.reason}</p>
              {p.signals.length > 0 && (
                <ul className="signals">
                  {p.signals.map((s) => <li key={s}>“{s}”</li>)}
                </ul>
              )}
              {p.matches_current ? (
                <span className="small ok-text">✓ Matches the current priority</span>
              ) : (
                <button className="btn ghost small" disabled={closed || applying} onClick={() => apply("priority")}>
                  Apply priority
                </button>
              )}
            </div>
          )}
          {both && (
            <button className="btn primary full" disabled={closed || applying} onClick={() => apply("both")}>
              {applying ? "Applying…" : "Apply both"}
            </button>
          )}
          <AiSource result={result} review="You decide whether to apply it" />
          <div className="suggestion-actions">
            <button className="link-btn small" onClick={suggest} disabled={busy}>{busy ? "Analyzing…" : "Ask again"}</button>
            <button className="link-btn small" onClick={() => setResult(null)}>Dismiss</button>
          </div>
        </div>
      )}
    </div>
  );
}
