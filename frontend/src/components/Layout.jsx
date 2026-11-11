import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { labels } from "../api";
import { useAuth } from "../auth";

const NAV = {
  end_user: [
    ["/tickets", "My tickets"],
    ["/tickets/new", "Submit a ticket"],
  ],
  agent: [["/queue", "My queue"]],
  admin: [["/admin", "Administration"]],
};

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden>◆</span>
          <span>Neural Support <b>Help Desk</b></span>
        </div>
        <nav>
          {NAV[user.role].map(([to, label]) => (
            <NavLink key={to} to={to} end>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="who">
          <span>
            {user.full_name} <span className="role-tag">{labels[user.role]}</span>
          </span>
          <button
            className="btn ghost"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
