import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    if (form.password !== form.confirm) return setError("Passwords do not match");
    setBusy(true);
    setError("");
    try {
      await api("/auth/register", { method: "POST", body: { full_name: form.full_name, email: form.email, password: form.password } });
      navigate("/login", { state: { registered: true } });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="card auth-card" onSubmit={submit}>
        <h1>Create an account</h1>
        {error && <div className="alert error">{error}</div>}
        <label>Full name<input value={form.full_name} onChange={set("full_name")} required /></label>
        <label>Email<input type="email" value={form.email} onChange={set("email")} required /></label>
        <label>Password<input type="password" minLength={8} value={form.password} onChange={set("password")} required /></label>
        <label>Confirm password<input type="password" minLength={8} value={form.confirm} onChange={set("confirm")} required /></label>
        <button className="btn primary full" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
        <p className="muted small">Already registered? <Link to="/login">Sign in</Link></p>
      </form>
    </div>
  );
}
