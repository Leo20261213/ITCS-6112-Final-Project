import { Fragment, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { AiSource, useAiFeatures } from "../components/Ai";

const STARTERS = ["I forgot my password", "My VPN keeps disconnecting", "How do I get new software?", "My laptop won't turn on"];
const MAX_TURNS = 12;

/** Renders the assistant's light markdown (paragraphs, numbered lines, **bold**) without innerHTML. */
function RichText({ text }) {
  return text.split(/\n{2,}/).map((para, i) => (
    <p key={i}>
      {para.split("\n").map((line, j) => (
        <Fragment key={j}>
          {j > 0 && <br />}
          {line.split(/(\*\*[^*]+\*\*)/g).map((part, k) =>
            part.startsWith("**") && part.endsWith("**") ? <b key={k}>{part.slice(2, -2)}</b> : <Fragment key={k}>{part}</Fragment>
          )}
        </Fragment>
      ))}
    </p>
  ));
}

function Source({ source }) {
  const [article, setArticle] = useState(null);
  const [open, setOpen] = useState(false);
  const toggle = async () => {
    if (!article) setArticle(await api(`/help/articles/${source.id}`).catch(() => null));
    setOpen((o) => !o);
  };
  return (
    <li>
      <button className="link-btn small" onClick={toggle} aria-expanded={open}>
        {open ? "▾" : "▸"} {source.title}
      </button>
      {open && article && (
        <div className="article">
          <RichText text={article.body} />
        </div>
      )}
    </li>
  );
}

// US-19: self-service help chatbot that answers from approved articles or hands off to support.
export default function AssistantPage() {
  const features = useAiFeatures();
  const navigate = useNavigate();
  const [turns, setTurns] = useState([]); // {role, content, meta?}
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [turns.length, busy]);

  const ask = async (text) => {
    const question = text.trim();
    if (!question || busy) return;
    const next = [...turns, { role: "user", content: question }];
    setTurns(next);
    setInput("");
    setBusy(true);
    setError("");
    let history = next.slice(-MAX_TURNS).map(({ role, content }) => ({ role, content }));
    while (history[0]?.role !== "user") history = history.slice(1);
    try {
      const r = await api("/assistant/chat", { method: "POST", body: { messages: history } });
      setTurns((t) => [...t, { role: "assistant", content: r.answer, meta: r }]);
    } catch (e) {
      setError(e.message);
      setTurns((t) => t.slice(0, -1));
      setInput(question);
    } finally {
      setBusy(false);
    }
  };

  const submitTicket = (draft) => navigate("/tickets/new", { state: { prefill: draft } });

  if (features && !features.chatbot) {
    return (
      <div className="card empty">
        <h2>The help assistant is turned off</h2>
        <p className="muted">Your administrator has disabled it. You can still <Link to="/tickets/new">submit a ticket</Link>.</p>
      </div>
    );
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Help assistant</h1>
          <p className="muted">Answers come from the help desk's approved articles. If it can't help, it will hand you over to a support agent.</p>
        </div>
        <Link to="/tickets/new" className="btn ghost">Submit a ticket</Link>
      </div>
      <section className="card chat">
        <ol className="chat-log" aria-live="polite">
          <li className="bubble bot">
            <p>Hi! Describe the problem you're having and I'll look for a fix in our help articles.</p>
            {turns.length === 0 && (
              <div className="starters">
                {STARTERS.map((s) => (
                  <button key={s} className="btn ghost small" onClick={() => ask(s)}>{s}</button>
                ))}
              </div>
            )}
          </li>
          {turns.map((t, i) =>
            t.role === "user" ? (
              <li key={i} className="bubble me"><p>{t.content}</p></li>
            ) : (
              <li key={i} className="bubble bot">
                <RichText text={t.content} />
                {t.meta.sources.length > 0 && (
                  <div className="sources">
                    <span className="muted small">From the help articles:</span>
                    <ul>{t.meta.sources.map((s) => <Source key={s.id} source={s} />)}</ul>
                  </div>
                )}
                {t.meta.escalate && t.meta.ticket_suggestion && (
                  <div className="handoff">
                    <p className="small"><b>Need a person?</b> I've drafted a ticket from this conversation for you to review.</p>
                    <button className="btn primary small" onClick={() => submitTicket(t.meta.ticket_suggestion)}>
                      Review and submit ticket
                    </button>
                  </div>
                )}
                <AiSource result={t.meta} review={t.meta.confident ? "Check the steps fit your situation" : "It may be incomplete"} />
              </li>
            )
          )}
          {busy && <li className="bubble bot typing" aria-label="Assistant is typing"><span /><span /><span /></li>}
          <li ref={endRef} aria-hidden className="thread-end" />
        </ol>
        {error && <div className="alert error">{error}</div>}
        <form
          className="chat-input"
          onSubmit={(e) => {
            e.preventDefault();
            ask(input);
          }}
        >
          <label className="sr-only" htmlFor="chat-q">Your question</label>
          <input
            id="chat-q"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            maxLength={2000}
            placeholder="Describe your problem…"
            autoComplete="off"
          />
          <button className="btn primary" disabled={busy || !input.trim()}>Ask</button>
        </form>
        <p className="muted small chat-foot">Never share passwords or one-time codes here.</p>
      </section>
    </>
  );
}
