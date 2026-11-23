import { BrandMark } from "./Icons";

const ROLES = [
  ["Employees", "submit requests, follow them, and get quick answers from the help assistant."],
  ["Support agents", "work their queue with AI triage, summaries, and reply drafts they approve."],
  ["Managers", "route tickets to the right agent and watch resolution trends."],
  ["Administrators", "manage access, categories, and how AI is used."],
];

/** Sign-in and registration frame: a spruce panel that explains the desk, and the form beside it. */
export default function AuthShell({ children }) {
  return (
    <div className="auth-page">
      <section className="auth-aside" aria-label="About this help desk">
        <span className="brand">
          <BrandMark size={34} />
          <span className="brand-text">
            <span className="brand-name">Neural Support</span>
            <span className="brand-sub">Help desk</span>
          </span>
        </span>
        <div className="auth-pitch">
          <h2>IT help that reaches the right person first time.</h2>
          <dl className="auth-roles">
            {ROLES.map(([who, what]) => (
              <div key={who}>
                <dt>{who}</dt>
                <dd>{what}</dd>
              </div>
            ))}
          </dl>
        </div>
        <p className="auth-foot">AI suggestions are always reviewed by a person before anything changes.</p>
      </section>
      <main className="auth-main">{children}</main>
    </div>
  );
}
