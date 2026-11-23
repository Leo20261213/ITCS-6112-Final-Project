import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { labels } from "../api";
import { useAuth } from "../auth";
import Icon, { BrandMark } from "./Icons";
import NotificationBell from "./NotificationBell";

// US-02: each role only sees the destinations it is allowed to use.
const NAV = {
  end_user: [
    { to: "/tickets", label: "My tickets", icon: "inbox" },
    { to: "/tickets/new", label: "Submit a ticket", icon: "plus" },
    { to: "/help", label: "Help assistant", icon: "chat" },
  ],
  agent: [{ to: "/queue", label: "My queue", icon: "queue" }],
  manager: [
    { to: "/manage", label: "Assignment board", icon: "board" },
    { to: "/analytics", label: "Analytics", icon: "chart" },
  ],
  admin: [
    { to: "/admin/analytics", label: "Analytics", icon: "chart" },
    { to: "/admin/tickets", label: "All tickets", icon: "tickets" },
    { to: "/admin/users", label: "Users & roles", icon: "users" },
    { to: "/admin/categories", label: "Categories", icon: "tag" },
    { to: "/admin/ai", label: "AI settings", icon: "spark" },
  ],
};

const SECTION = { end_user: "Support", agent: "Workspace", manager: "Team", admin: "Administration" };

const initials = (name) =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");

const MOBILE = "(max-width: 860px)";

/** True while the viewport is phone/tablet width, so only one notification bell is mounted (and polling). */
function useIsMobile() {
  const [mobile, setMobile] = useState(() => window.matchMedia(MOBILE).matches);
  useEffect(() => {
    const mq = window.matchMedia(MOBILE);
    const on = () => setMobile(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return mobile;
}

function readCollapsed() {
  try {
    return localStorage.getItem("nav-collapsed") === "1";
  } catch {
    return false;
  }
}

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [drawer, setDrawer] = useState(false);
  const mobile = useIsMobile();

  useEffect(() => {
    try {
      localStorage.setItem("nav-collapsed", collapsed ? "1" : "0");
    } catch {
      /* storage unavailable: the preference just isn't remembered */
    }
  }, [collapsed]);

  // Close the mobile drawer whenever the route changes, and on Escape.
  useEffect(() => setDrawer(false), [location.pathname]);
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e) => e.key === "Escape" && setDrawer(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawer]);

  const signOut = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className={`shell${collapsed ? " collapsed" : ""}${drawer ? " drawer-open" : ""}`}>
      <a href="#main" className="skip-link">Skip to content</a>

      <header className="mobilebar">
        <button className="icon-only" onClick={() => setDrawer(true)} aria-label="Open navigation" aria-expanded={drawer}>
          <Icon name="menu" size={22} />
        </button>
        <span className="brand">
          <BrandMark size={26} />
          <span className="brand-name">Neural Support</span>
        </span>
        {mobile && <NotificationBell compact />}
      </header>

      <div className="scrim" onClick={() => setDrawer(false)} aria-hidden />

      <aside className="sidebar" aria-label="Primary">
        <div className="sidebar-top">
          <span className="brand">
            <BrandMark />
            <span className="brand-text">
              <span className="brand-name">Neural Support</span>
              <span className="brand-sub">Help desk</span>
            </span>
          </span>
          <button className="icon-only drawer-close" onClick={() => setDrawer(false)} aria-label="Close navigation">
            <Icon name="close" size={20} />
          </button>
        </div>

        <nav className="side-nav">
          <p className="nav-section">{SECTION[user.role]}</p>
          <ul>
            {NAV[user.role].map((item) => (
              <li key={item.to}>
                <NavLink to={item.to} end title={collapsed ? item.label : undefined}>
                  <Icon name={item.icon} />
                  <span className="nav-label">{item.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="sidebar-foot">
          {!mobile && <NotificationBell collapsed={collapsed} />}
          <div className="me">
            <span className="avatar" aria-hidden>{initials(user.full_name)}</span>
            <span className="me-text">
              <span className="me-name">{user.full_name}</span>
              <span className="me-role">{labels[user.role]}</span>
            </span>
            <button className="icon-only" onClick={signOut} aria-label="Sign out" title="Sign out">
              <Icon name="logout" />
            </button>
          </div>
          <button
            className="collapse-btn"
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <Icon name={collapsed ? "expand" : "collapse"} />
            <span className="nav-label">Collapse</span>
          </button>
        </div>
      </aside>

      <main id="main" className="content" tabIndex={-1}>
        <div className="content-inner">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
