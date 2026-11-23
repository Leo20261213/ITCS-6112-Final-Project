"""Thin wrapper around the Anthropic SDK: one structured-output request per AI feature.

Every call asks Claude for JSON that matches a schema (structured outputs), so the
result can be validated before anything is shown to a user. Failures are raised as
`ClaudeError` so the service layer can fall back to the built-in rules or report them.
"""
import json
from typing import Any

import anthropic

from ..models import AiSettings

# Models an administrator may choose (US-21). Haiku is the default: intake, triage, summaries,
# reply drafts and the help chatbot are short, well-structured tasks, and it costs a fraction of
# the larger models ($0.10 / $0.50 per million input / output tokens, against $4 / $20 for Opus).
DEFAULT_MODEL = "claude-haiku-5-5"
MODELS = {
    "claude-haiku-5-5": "Claude Haiku 5.5 (lowest cost, default)",
    "claude-sonnet-5-5": "Claude Sonnet 5.5 (balanced)",
    "claude-opus-5-5": "Claude Opus 5.5 (most capable, highest cost)",
}
# Server-side refusal fallback is available for these models; Haiku 5.5 has none.
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}
_FALLBACK_BETA = "server-side-fallback-2026-07-01"

_client: anthropic.Anthropic | None = None


class ClaudeError(Exception):
    """Claude could not produce a usable answer. `reason` is safe to show to staff."""

    def __init__(self, reason: str, not_configured: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.not_configured = not_configured


def get_client() -> anthropic.Anthropic:
    """Credentials resolve from the environment (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN,
    or an `ant auth login` profile). Tests replace this function with a fake."""
    global _client
    if _client is None:
        _client = anthropic.Anthropic(timeout=45.0, max_retries=1)
    return _client


def call_structured(
    settings: AiSettings,
    *,
    system: str | list[dict[str, Any]],
    messages: list[dict[str, Any]],
    schema: dict[str, Any],
    effort: str = "low",
    max_tokens: int = 8000,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Send one request and return the parsed JSON object Claude produced.

    Thinking is always on for the current models and counts toward max_tokens, so the
    limits are set with room for it. `timeout` (seconds) overrides the client default for
    requests a person is waiting on, such as ticket submission."""
    kwargs: dict[str, Any] = {
        "model": settings.model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": messages,
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    if settings.model in _FALLBACK_MODELS:
        kwargs["betas"] = [_FALLBACK_BETA]
        kwargs["fallbacks"] = "default"

    try:
        response = get_client().beta.messages.create(**kwargs)
    except TypeError as e:  # raised locally when no credentials can be resolved
        if "authentication" in str(e).lower():
            raise ClaudeError("Claude is not configured on this server (no API credentials)", not_configured=True) from e
        raise
    except anthropic.AuthenticationError as e:
        raise ClaudeError("Claude rejected the server's API credentials", not_configured=True) from e
    except anthropic.PermissionDeniedError as e:
        raise ClaudeError("The server's API key is not permitted to use this model") from e
    except anthropic.NotFoundError as e:
        raise ClaudeError(f"Model '{settings.model}' is not available to this account") from e
    except anthropic.RateLimitError as e:
        raise ClaudeError("Claude is rate limiting requests right now") from e
    except anthropic.APIStatusError as e:
        raise ClaudeError(f"Claude returned an error ({e.status_code})") from e
    except anthropic.APIConnectionError as e:
        raise ClaudeError("Could not reach Claude (network error or timeout)") from e

    if response.stop_reason == "refusal":
        raise ClaudeError("Claude declined to answer this request")
    if response.stop_reason == "max_tokens":
        raise ClaudeError("Claude's answer was cut off")
    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise ClaudeError("Claude returned no answer")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ClaudeError("Claude returned malformed output") from e
    if not isinstance(data, dict):
        raise ClaudeError("Claude returned malformed output")
    return data
