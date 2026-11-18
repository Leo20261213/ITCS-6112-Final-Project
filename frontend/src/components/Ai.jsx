import { useEffect, useState } from "react";
import { api } from "../api";

const MODEL_NAMES = {
  "claude-opus-5-5": "Claude Opus 5.5",
  "claude-sonnet-5-5": "Claude Sonnet 5.5",
  "claude-haiku-5-5": "Claude Haiku 5.5",
};

/** US-21: which AI features the administrator has switched on. */
export function useAiFeatures() {
  const [features, setFeatures] = useState(null);
  useEffect(() => {
    api("/ai/features").then(setFeatures).catch(() => setFeatures({ enabled: false }));
  }, []);
  return features;
}

/** Every AI output says where it came from and that a person decides what to do with it. */
export function AiSource({ result, review = "Review before using" }) {
  if (!result) return null;
  const by = result.source === "claude" ? MODEL_NAMES[result.model] || result.model : "built-in rules";
  return (
    <div className="ai-source">
      <span className="ai-tag" aria-hidden>AI</span>
      <span>
        Suggested by {by}. {review}.
      </span>
      {result.notice && <span className="ai-notice">{result.notice}</span>}
    </div>
  );
}

export const pct = (x) => `${Math.round(x * 100)}%`;
