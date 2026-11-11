import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, labels } from "../api";

// US-03: submit a support ticket (with US-05 category + priority)
export default function NewTicketPage() {
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);
  const [priorities, setPriorities] = useState([]);
  const [form, setForm] = useState({ title: "", description: "", category_id: "", priority: "medium" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

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
      const t = await api("/tickets", { method: "POST", body: { ...form, category_id: Number(form.category_id) } });
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
        {error && <div className="alert error">{error}</div>}
        <label>
          Title
          <input value={form.title} onChange={set("title")} minLength={3} maxLength={200} placeholder="Short summary of the issue" required />
        </label>
        <div className="row">
          <label>
            Category
            <select value={form.category_id} onChange={set("category_id")} required>
              <option value="" disabled>Select a category</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
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
          <button className="btn primary" disabled={busy}>{busy ? "Submitting…" : "Submit ticket"}</button>
        </div>
      </form>
    </>
  );
}
