import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { homeFor, useAuth } from "../auth";

const DEMO = [
  ["End user", "user1@helpdesk.local"],
  ["Support agent", "agent1@helpdesk.local"],
  ["Administrator", "admin@helpdesk.local"],
];

// US-01: secure login
export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homeFor(user.role)} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const u = await login(email, password);
      navigate(homeFor(u.role), { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="card auth-card" onSubmit={submit}>
        <div className="brand big">
          <span className="logo" aria-hidden>◆</span>
          <span>Neural Support <b>Help Desk</b></span>
        </div>
        <h1>Sign in</h1>
        {location.state?.registered && <div className="alert success">Account created. Please sign in.</div>}
        {error && <div className="alert error">{error}</div>}
        <label>
          Email
          <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Password
          <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </label>
        <button className="btn primary full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        <p className="muted small">
          No account? <Link to="/register">Create one</Link>
        </p>
        <div className="demo">
          <p className="small muted">Demo accounts (password <code>Password123!</code>)</p>
          <div className="demo-buttons">
            {DEMO.map(([label, em]) => (
              <button type="button" key={em} className="btn ghost small" onClick={() => { setEmail(em); setPassword("Password123!"); }}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </form>
    </div>
  );
}
