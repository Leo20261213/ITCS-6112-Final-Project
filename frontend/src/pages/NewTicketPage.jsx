import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, labels } from "../api";
import { useAiFeatures } from "../components/Ai";

// US-03: submit a support ticket (with US-05 category + priority)
export default function NewTicketPage() {
  const navigate = useNavigate();
  const prefill = useLocation().state?.prefill; // US-19: drafted by the help assistant
  const [categories, setCategories] = useState([]);
  const [priorities, setPriorities] = useState([]);
  const [form, setForm] = useState({
    title: prefill?.title ?? "",
    description: prefill?.description ?? "",
    category_id: prefill?.category_id ? String(prefill.category_id) : "",
    priority: "medium",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const features = useAiFeatures();
  const auto = Boolean(features?.intake); // the help desk categorizes and routes new tickets itself

  useEffect(() => {
    api("/categories").then(setCategories).catch((e) => setError(e.message));
    api("/meta").then((m) => setPriorities(m.priorities)).catch(() => {});
  }, []);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = { ...form, category_id: form.category_id ? Number(form.category_id) : null };
      const t = await api("/tickets", { method: "POST", body });
      navigate(`/tickets/${t.id}`, { state: { created: true } });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Submit a ticket</h1>
          <p className="muted">Describe the problem and a support agent will pick it up.</p>
        </div>
      </div>
      <form className="card form" onSubmit={submit}>
        {prefill && <div className="alert info">The help assistant filled this in from your conversation. Check it and add anything that's missing.</div>}
        {error && <div className="alert error">{error}</div>}
        <label>
          Title
          <input value={form.title} onChange={set("title")} minLength={3} maxLength={200} placeholder="Short summary of the issue" required />
        </label>
        <div className="row">
          <label>
            Category
            <select value={form.category_id} onChange={set("category_id")} required={!auto}>
              <option value="" disabled={!auto}>{auto ? "Choose for me (recommended)" : "Select a category"}</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            {auto && !form.category_id && (
              <span className="muted small">The help desk will file it under the right category and send it to an agent.</span>
            )}
          </label>
          <label>
            Priority
            <select value={form.priority} onChange={set("priority")}>
              {priorities.map((p) => <option key={p} value={p}>{labels[p]}</option>)}
            </select>
          </label>
        </div>
        <label>
          Description
          <textarea
            rows={7}
            value={form.description}
            onChange={set("description")}
            minLength={10}
            maxLength={5000}
            placeholder="What happened, when it started, and anything you've already tried"
            required
          />
        </label>
        <div className="actions">
          <button type="button" className="btn ghost" onClick={() => navigate(-1)}>Cancel</button>
          <button className="btn primary" disabled={busy || !features}>{busy ? (auto ? "Submitting and routing…" : "Submitting…") : "Submit ticket"}</button>
        </div>
      </form>
    </>
  );
}
