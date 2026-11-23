"""Live check that the help desk can reach Claude.

Sends one real request through the same code the app uses (app/ai/claude.py), asking
Claude to categorize and route a sample ticket, and prints what came back.

    cd backend
    .venv\\Scripts\\python -m scripts.check_claude            # macOS/Linux: .venv/bin/python -m scripts.check_claude
    .venv\\Scripts\\python -m scripts.check_claude claude-opus-5-5     # try another model

Credentials come from ANTHROPIC_API_KEY (in the environment or backend/.env), as in the app.
Exit code 0 means Claude answered with valid structured output.
"""
import sys
import time
from types import SimpleNamespace

from app import database  # noqa: F401  (loads backend/.env)
from app.ai import claude

CATEGORIES = ["Account Access", "Hardware", "Network", "Other", "Software"]
TICKET = (
    "<ticket>\n<title>Locked out after password change</title>\n<description>\n"
    "I changed my password this morning and now every sign-in says my account is locked. "
    "I can't get into email or Teams and have a client call at 2pm.\n</description>\n</ticket>"
)


def main() -> int:
    model = sys.argv[1] if len(sys.argv) > 1 else claude.DEFAULT_MODEL
    settings = SimpleNamespace(model=model)
    schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": CATEGORIES},
            "category_reason": {"type": "string"},
            "assignee": {"type": "string", "enum": ["A1", "A2"]},
            "routing_reason": {"type": "string"},
        },
        "required": ["category", "category_reason", "assignee", "routing_reason"],
        "additionalProperties": False,
    }
    system = (
        "You run intake for an IT help desk. Choose the category that best fits the ticket, then the support agent "
        "who should handle it, preferring the one with fewer active tickets unless experience clearly matters. "
        "One short sentence per reason.\n\nSupport agents:\n- A1: 4 active tickets; recent: Hardware 6\n"
        "- A2: 2 active tickets; recent: Account Access 5, Network 1"
    )
    print(f"Calling {model}...")
    start = time.monotonic()
    try:
        data = claude.call_structured(settings, system=system, schema=schema, effort="low", max_tokens=8000,
                                      timeout=60, messages=[{"role": "user", "content": TICKET}])
    except claude.ClaudeError as e:
        print(f"FAILED: {e.reason}")
        if e.not_configured:
            print("Set ANTHROPIC_API_KEY in backend/.env (see .env.example), then run this again.")
        return 1
    print(f"OK in {time.monotonic() - start:.1f}s")
    for key, value in data.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
