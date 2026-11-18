import { useEffect, useState } from "react";
import { api, labels, ROLES } from "../api";
import { useAuth } from "../auth";
import AssignmentBoard from "../components/AssignmentBoard";
import AnalyticsDashboard from "../components/AnalyticsDashboard";
import AiSettingsPanel from "../components/AiSettingsPanel";

// US-02: role-based access management; US-05: category management
export default function AdminPage() {
  const [tab, setTab] = useState("analytics");
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Administration</h1>
          <p className="muted">Monitor support performance, manage access and categories, and configure AI assistance.</p>
        </div>
      </div>
      <div className="tabs" role="tablist">
        {[["analytics", "Analytics"], ["users", "Users & roles"], ["categories", "Categories"], ["tickets", "All tickets"], ["ai", "AI settings"]].map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>
            {l}
          </button>
        ))}
      </div>
      {tab === "users" && <UsersPanel />}
      {tab === "categories" && <CategoriesPanel />}
      {tab === "tickets" && <AssignmentBoard />}
      {tab === "analytics" && <AnalyticsDashboard />}
      {tab === "ai" && <AiSettingsPanel />}
    </>
  );
}

function UsersPanel() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/admin/users").then(setUsers).catch((e) => setError(e.message));
  }, []);

  const patch = async (id, body) => {
    setError("");
    try {
      const updated = await api(`/admin/users/${id}`, { method: "PATCH", body });
      setUsers((us) => us.map((u) => (u.id === id ? updated : u)));
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="card">
      {error && <div className="alert error">{error}</div>}
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const self = u.id === me.id;
              return (
                <tr key={u.id} className={u.is_active ? "" : "inactive"}>
                  <td>{u.full_name}{self && <span className="muted small"> (you)</span>}</td>
                  <td>{u.email}</td>
                  <td>
                    <select value={u.role} disabled={self} onChange={(e) => patch(u.id, { role: e.target.value })} aria-label={`Role for ${u.full_name}`}>
                      {ROLES.map((r) => <option key={r} value={r}>{labels[r]}</option>)}
                    </select>
                  </td>
                  <td>{u.is_active ? <span className="badge status-resolved">Active</span> : <span className="badge neutral">Deactivated</span>}</td>
                  <td className="right">
                    {!self && (
                      <button className="btn ghost small" onClick={() => patch(u.id, { is_active: !u.is_active })}>
                        {u.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CategoriesPanel() {
  const [cats, setCats] = useState([]);
  const [form, setForm] = useState({ name: "", description: "" });
  const [error, setError] = useState("");

  const load = () => api("/categories").then(setCats).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const add = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await api("/admin/categories", { method: "POST", body: form });
      setForm({ name: "", description: "" });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const remove = async (id) => {
    setError("");
    try {
      await api(`/admin/categories/${id}`, { method: "DELETE" });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="card">
      {error && <div className="alert error">{error}</div>}
      <form className="inline-form" onSubmit={add}>
        <input placeholder="Category name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        <input placeholder="Description (optional)" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <button className="btn primary">Add category</button>
      </form>
      <ul className="cat-list">
        {cats.map((c) => (
          <li key={c.id}>
            <div>
              <b>{c.name}</b>
              {c.description && <div className="muted small">{c.description}</div>}
            </div>
            <button className="btn ghost small" onClick={() => remove(c.id)}>Remove</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
