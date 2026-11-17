const TOKEN_KEY = "helpdesk_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY));

let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => (onUnauthorized = fn);

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function errorMessage(body, fallback) {
  if (!body) return fallback;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) {
    return body.detail.map((d) => `${d.loc?.slice(1).join(".") || "field"}: ${d.msg}`).join("; ");
  }
  return fallback;
}

export async function api(path, { method = "GET", body, form, multipart } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (multipart) {
    payload = multipart; // FormData: the browser sets the multipart boundary header itself
  } else if (form) {
    payload = new URLSearchParams(form);
    headers["Content-Type"] = "application/x-www-form-urlencoded";
  } else if (body !== undefined) {
    payload = JSON.stringify(body);
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`/api${path}`, { method, headers, body: payload });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && token) onUnauthorized();
    throw new ApiError(res.status, errorMessage(data, `Request failed (${res.status})`));
  }
  return data;
}

export const labels = {
  open: "Open",
  in_progress: "In progress",
  on_hold: "On hold",
  resolved: "Resolved",
  closed: "Closed",
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
  end_user: "End user",
  agent: "Support agent",
  manager: "Manager",
  admin: "Administrator",
};

export const ROLES = ["end_user", "agent", "manager", "admin"];

/** US-13: attachments need the bearer token, so fetch them and hand the browser a blob. */
export async function downloadFile(path, filename) {
  const res = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    if (res.status === 401) onUnauthorized();
    throw new ApiError(res.status, errorMessage(data, `Download failed (${res.status})`));
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const fmtBytes = (n) =>
  n < 1024 ? `${n} B` : n < 1024 * 1024 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`;

const toDate = (iso) => new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);

export const fmtRelative = (iso) => {
  const s = Math.round((Date.now() - toDate(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 7 * 86400) return `${Math.floor(s / 86400)} d ago`;
  return fmtDate(iso);
};

export const fmtDate = (iso) =>
  toDate(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
