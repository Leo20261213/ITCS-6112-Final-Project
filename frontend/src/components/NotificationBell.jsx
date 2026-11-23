import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, fmtRelative } from "../api";
import Icon from "./Icons";

const POLL_MS = 20000;

// US-14: in-app notifications about tickets the user is associated with.
// `compact` renders an icon button for the mobile top bar; otherwise it is a sidebar row.
export default function NotificationBell({ compact = false, collapsed = false }) {
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
    <div className={`notif${compact ? " notif-compact" : " notif-side"}`} ref={ref}>
      <button
        className={compact ? "icon-only bell" : "side-row bell"}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={data.unread ? `Notifications, ${data.unread} unread` : "Notifications"}
        title={collapsed ? "Notifications" : undefined}
      >
        <Icon name="bell" size={compact ? 22 : 18} />
        {!compact && <span className="nav-label">Notifications</span>}
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
