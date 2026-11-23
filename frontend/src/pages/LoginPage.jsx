import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { homeFor, useAuth } from "../auth";
import AuthShell from "../components/AuthShell";

const DEMO = [
  ["End user", "user1@helpdesk.local"],
  ["Support agent", "agent1@helpdesk.local"],
  ["Manager", "manager@helpdesk.local"],
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
    <AuthShell>
      <form className="auth-card" onSubmit={submit}>
        <div>
          <h1>Sign in</h1>
          <p className="muted">Use your work email to reach your tickets.</p>
        </div>
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
          <p className="small muted">Try a demo account. Each one signs in with <code>Password123!</code></p>
          <div className="demo-buttons">
            {DEMO.map(([label, em]) => (
              <button type="button" key={em} className="btn ghost small" onClick={() => { setEmail(em); setPassword("Password123!"); }}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </form>
    </AuthShell>
  );
}
