import { useEffect, useState } from "react";
import { api, fmtDate, fmtRelative } from "../api";

const FEATURES = [
  ["category_suggestions", "Category suggestions", "Agents can ask AI to suggest a ticket's category (US-15)."],
  ["priority_suggestions", "Urgency and priority suggestions", "Agents can ask AI to flag urgency and suggest a priority (US-16)."],
  ["summaries", "Ticket summaries", "Agents can summarize long ticket conversations (US-17)."],
  ["reply_suggestions", "Reply drafts", "Agents can draft replies with AI, then edit and send them themselves (US-18)."],
  ["chatbot", "Help assistant chatbot", "End users can ask the assistant, which answers only from approved help articles (US-19)."],
];
const PROVIDERS = [
  ["auto", "Claude, with built-in fallback", "Use Claude; if it's unavailable, use the built-in rules and label the result."],
  ["claude", "Claude only", "Use Claude; if it's unavailable, show an error instead of a fallback."],
  ["local", "Built-in rules only", "Keyword rules on this server. No ticket data leaves the help desk."],
];
const FEATURE_NAMES = { triage: "Triage", summary: "Summary", reply: "Reply draft", chatbot: "Chatbot" };

// US-21: administrators configure AI assistance so it can be managed responsibly.
export default function AiSettingsPanel() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState(null);
  const [usage, setUsage] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const loadUsage = () => api("/admin/ai-usage?limit=25").then(setUsage).catch(() => {});
  useEffect(() => {
    api("/admin/ai-settings")
      .then((d) => {
        setData(d);
        setForm(d.settings);
      })
      .catch((e) => setError(e.message));
    loadUsage();
  }, []);

  if (!form) return error ? <div className="alert error">{error}</div> : <p className="muted">Loading…</p>;

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const dirty = Object.keys(form).some((k) => !["updated_at", "updated_by"].includes(k) && form[k] !== data.settings[k]);
  const usesClaude = form.provider !== "local";

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    const body = {};
    for (const k of Object.keys(form)) if (!["updated_at", "updated_by"].includes(k) && form[k] !== data.settings[k]) body[k] = form[k];
    try {
      const d = await api("/admin/ai-settings", { method: "PUT", body });
      setData(d);
      setForm(d.settings);
      setNotice("AI settings saved. They apply to the next AI request.");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <form className="card ai-settings" onSubmit={save}>
        {notice && <div className="alert success" role="status">{notice}</div>}
        {error && <div className="alert error">{error}</div>}

        <label className="switch-row master">
          <input type="checkbox" checked={form.enabled} onChange={(e) => set("enabled", e.target.checked)} />
          <span>
            <b>AI assistance</b>
            <span className="muted small">Turn off to disable every AI feature for everyone.</span>
          </span>
        </label>

        <fieldset disabled={!form.enabled}>
          <legend>Features</legend>
          {FEATURES.map(([key, label, help]) => (
            <label key={key} className="switch-row">
              <input type="checkbox" checked={form[key]} onChange={(e) => set(key, e.target.checked)} />
              <span>
                {label}
                <span className="muted small">{help}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <fieldset disabled={!form.enabled}>
          <legend>Provider</legend>
          {PROVIDERS.map(([value, label, help]) => (
            <label key={value} className="switch-row">
              <input type="radio" name="provider" value={value} checked={form.provider === value} onChange={() => set("provider", value)} />
              <span>
                {label}
                <span className="muted small">{help}</span>
              </span>
            </label>
          ))}
          {usesClaude && !data.claude_credentials_detected && (
            <p className="alert info small">
              No Claude API credentials were found on the server. Set <code>ANTHROPIC_API_KEY</code> in the backend's environment
              {form.provider === "auto" ? "; until then the built-in rules are used." : ", or AI requests will fail."}
            </p>
          )}
          <label className="field">
            Claude model
            <select value={form.model} onChange={(e) => set("model", e.target.value)} disabled={!usesClaude}>
              {Object.entries(data.models).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
            </select>
          </label>
        </fieldset>

        <fieldset disabled={!form.enabled}>
          <legend>Privacy and guidance</legend>
          <label className="switch-row">
            <input type="checkbox" checked={form.share_personal_data} onChange={(e) => set("share_personal_data", e.target.checked)} />
            <span>
              Share names and contact details with Claude
              <span className="muted small">
                Off (recommended): names, email addresses and phone numbers are replaced before ticket text is sent.
              </span>
            </span>
          </label>
          <label className="field">
            Reply guidance for AI drafts
            <textarea
              rows={3}
              maxLength={500}
              value={form.reply_guidance}
              onChange={(e) => set("reply_guidance", e.target.value)}
              placeholder="For example: Keep replies under 120 words and link to the self-service portal when relevant."
            />
            <span className="muted small">{form.reply_guidance.length}/500</span>
          </label>
        </fieldset>

        <div className="actions">
          {data.settings.updated_by && (
            <span className="muted small grow">
              Last changed by {data.settings.updated_by.full_name}, {fmtDate(data.settings.updated_at)}
            </span>
          )}
          <button type="button" className="btn ghost" disabled={!dirty || busy} onClick={() => setForm(data.settings)}>Discard</button>
          <button className="btn primary" disabled={!dirty || busy}>{busy ? "Saving…" : "Save settings"}</button>
        </div>
      </form>

      <section className="card">
        <div className="card-head">
          <h3>Recent AI activity</h3>
          <button className="link-btn small" onClick={loadUsage}>Refresh</button>
        </div>
        <p className="muted small">Who used which feature and how it was answered. Ticket content is never stored here.</p>
        {!usage ? (
          <p className="muted small">Loading…</p>
        ) : usage.items.length === 0 ? (
          <p className="muted small">No AI requests yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr><th>When</th><th>Feature</th><th>User</th><th>Ticket</th><th>Answered by</th><th>Outcome</th><th className="num">Time</th></tr>
              </thead>
              <tbody>
                {usage.items.map((u) => (
                  <tr key={u.id}>
                    <td className="nowrap" title={fmtDate(u.created_at)}>{fmtRelative(u.created_at)}</td>
                    <td>{FEATURE_NAMES[u.feature] ?? u.feature}</td>
                    <td>{u.user.full_name}</td>
                    <td>{u.ticket_id ? `#${u.ticket_id}` : "—"}</td>
                    <td>{u.source === "claude" ? u.model : "Built-in rules"}</td>
                    <td title={u.note || undefined}>
                      <span className={`badge ${u.outcome === "ok" ? "status-resolved" : u.outcome === "fallback" ? "status-in_progress" : "prio-critical"}`}>
                        {u.outcome === "ok" ? "OK" : u.outcome === "fallback" ? "Fell back" : "Failed"}
                      </span>
                      {u.note && <div className="muted small">{u.note}</div>}
                    </td>
                    <td className="num">{u.latency_ms} ms</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
