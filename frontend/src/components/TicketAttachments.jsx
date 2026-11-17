import { useCallback, useEffect, useRef, useState } from "react";
import { api, downloadFile, fmtBytes, fmtRelative } from "../api";

// US-13: attach screenshots and supporting files to a ticket.
export default function TicketAttachments({ ticket, rules, onActivity }) {
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);
  const closed = ticket.status === "closed";

  const load = useCallback(
    () => api(`/tickets/${ticket.id}/attachments`).then(setItems).catch((e) => setError(e.message)),
    [ticket.id]
  );
  useEffect(() => {
    load();
  }, [load]);

  const upload = async (file) => {
    setError("");
    const ext = file.name.includes(".") ? file.name.split(".").pop().toLowerCase() : "";
    if (rules && !rules.allowed_extensions.includes(ext)) {
      return setError(`“${file.name}” is not an allowed file type.`);
    }
    if (rules && file.size > rules.max_bytes) {
      return setError(`“${file.name}” is ${fmtBytes(file.size)}; the limit is ${fmtBytes(rules.max_bytes)}.`);
    }
    const fd = new FormData();
    fd.append("file", file);
    setBusy(true);
    try {
      const a = await api(`/tickets/${ticket.id}/attachments`, { method: "POST", multipart: fd });
      setItems((xs) => [...(xs || []), a]);
      onActivity?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const download = (a) => downloadFile(`/attachments/${a.id}`, a.filename).catch((e) => setError(e.message));
  const full = rules && items && items.length >= rules.max_per_ticket;

  return (
    <section className="card">
      <div className="card-head">
        <h3>Attachments</h3>
        {!closed && !full && (
          <>
            <input
              ref={inputRef}
              type="file"
              className="sr-only"
              id="attach-input"
              accept={rules?.allowed_extensions.map((e) => `.${e}`).join(",")}
              onChange={(e) => e.target.files[0] && upload(e.target.files[0])}
            />
            <button type="button" className="btn ghost small" disabled={busy} onClick={() => inputRef.current?.click()}>
              {busy ? "Uploading…" : "Attach a file"}
            </button>
          </>
        )}
      </div>
      {error && <div className="alert error">{error}</div>}
      {!items ? (
        <p className="muted small">Loading…</p>
      ) : items.length === 0 ? (
        <p className="muted small">No files attached.</p>
      ) : (
        <ul className="files">
          {items.map((a) => (
            <li key={a.id}>
              <button className="link-btn file-name" onClick={() => download(a)} title="Download">{a.filename}</button>
              <span className="muted small">
                {fmtBytes(a.size)} · {a.uploaded_by.full_name} · {fmtRelative(a.created_at)}
              </span>
            </li>
          ))}
        </ul>
      )}
      {rules && !closed && (
        <p className="muted small hint">
          {full
            ? `This ticket has reached the limit of ${rules.max_per_ticket} files.`
            : `Up to ${fmtBytes(rules.max_bytes)} each: ${rules.allowed_extensions.join(", ")}.`}
        </p>
      )}
    </section>
  );
}
