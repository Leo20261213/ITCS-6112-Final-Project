import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, fmtRelative } from "../api";

const POLL_MS = 20000;

// US-14: in-app notifications about tickets the user is associated with.
export default function NotificationBell() {
  const [data, setData] = useState({ unread: 0, items: [] });
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();

  const load = useCallback(() => api("/notifications?limit=20").then(setData).catch(() => {}), []);

  // Poll while the tab is visible, and refresh on navigation so changes show up promptly.
  useEffect(() => {
    load();
    const id = setInterval(() => document.visibilityState === "visible" && load(), POLL_MS);
    return () => clearInterval(id);
  }, [load, location.pathname]);

  useEffect(() => {
    if (!open) return;
    const onClick = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const openItem = async (n) => {
    setOpen(false);
    if (!n.is_read) await api(`/notifications/${n.id}/read`, { method: "POST" }).catch(() => {});
    load();
    if (n.ticket_id) navigate(`/tickets/${n.ticket_id}`);
  };

  const readAll = async () => {
    await api("/notifications/read-all", { method: "POST" }).catch(() => {});
    load();
  };

  return (
    <div className="notif" ref={ref}>
      <button
        className="btn ghost icon-btn"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={data.unread ? `Notifications, ${data.unread} unread` : "Notifications"}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {data.unread > 0 && <span className="notif-count">{data.unread > 99 ? "99+" : data.unread}</span>}
      </button>
      {open && (
        <div className="notif-panel" role="dialog" aria-label="Notifications">
          <div className="notif-head">
            <b>Notifications</b>
            {data.unread > 0 && (
              <button className="link-btn" onClick={readAll}>Mark all as read</button>
            )}
          </div>
          {data.items.length === 0 ? (
            <p className="muted small notif-empty">You're all caught up. Updates to your tickets will appear here.</p>
          ) : (
            <ul>
              {data.items.map((n) => (
                <li key={n.id}>
                  <button className={`notif-item${n.is_read ? "" : " unread"}`} onClick={() => openItem(n)}>
                    <span>{n.message}</span>
                    <span className="muted small">{fmtRelative(n.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
