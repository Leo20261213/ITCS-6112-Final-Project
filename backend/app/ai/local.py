"""Built-in, rule-based fallback for every AI feature.

Used when an administrator selects the offline provider, when Claude is not configured,
or (in automatic mode) when a Claude request fails. Deterministic and explainable, so
results are always labelled as coming from built-in rules rather than Claude.
"""
import re
from collections.abc import Sequence

from ..models import Category, HelpArticle, Priority

WORD = re.compile(r"[a-z0-9']+")

STOPWORDS = set(
    """a an and are as at be been but by can cant could do does doesnt dont for from get getting got had has have how i
    im is it its just me my no not of on or our please so some that the their them then there this to too up us was we
    were what when where which while who why will with would you your hi hello hey thanks thank help need want still
    any anything also again since after before into out about all am did ive id in if as be its every few some very really
    keeps keep now today yesterday new""".split()
)

# Keyword cues for the default categories. Admin-created categories still match on their
# own name and description words.
CATEGORY_CUES: dict[str, list[str]] = {
    "hardware": ["laptop", "monitor", "screen", "printer", "keyboard", "mouse", "dock", "battery", "charger", "power",
                 "headset", "webcam", "hardware", "desktop", "pc", "toner", "jam", "display", "usb", "broken", "cracked"],
    "software": ["install", "license", "licence", "software", "application", "app", "update", "crash", "crashes", "excel",
                 "word", "outlook", "adobe", "acrobat", "teams", "zoom", "error", "upgrade", "version", "program"],
    "network": ["vpn", "wifi", "wi-fi", "wireless", "network", "internet", "connection", "connect", "disconnect",
                "disconnects", "ethernet", "dns", "slow", "latency", "router", "offline", "bandwidth"],
    "account access": ["password", "locked", "lockout", "login", "log", "sign", "mfa", "2fa", "authenticator",
                       "account", "access", "permission", "permissions", "reset", "expired", "credentials", "sso"],
}

CRITICAL_CUES = ["outage", "down for everyone", "everyone", "whole team", "entire", "security", "breach", "phishing",
                 "virus", "malware", "ransomware", "data loss", "lost data", "hacked", "compromised", "production"]
HIGH_CUES = ["cannot work", "can't work", "cant work", "unable to work", "urgent", "asap", "deadline", "locked out",
             "won't turn on", "will not power", "not power", "does not turn on", "doesn't turn on", "blocked",
             "cannot access", "can't access", "cant access", "stopped working", "not working", "dead"]
LOW_CUES = ["request", "would like", "nice to have", "when you get a chance", "no rush", "question", "how do i",
            "install", "license", "new software", "access to", "wondering"]

PRIORITY_ORDER = [Priority.LOW, Priority.MEDIUM, Priority.HIGH, Priority.CRITICAL]


def words(text: str) -> list[str]:
    return [w for w in WORD.findall(text.lower()) if len(w) > 1 and w not in STOPWORDS]


def suggest_category(text: str, categories: Sequence[Category]) -> tuple[Category | None, float, str]:
    """Pick the category whose cues best match the text. Returns (category, confidence, reason)."""
    lowered = text.lower()
    tokens = set(words(text))
    best, best_score, best_hits = None, 0.0, []
    for cat in categories:
        cues = set(CATEGORY_CUES.get(cat.name.lower(), [])) | set(words(f"{cat.name} {cat.description}"))
        hits = sorted(c for c in cues if (c in tokens if " " not in c and "-" not in c else c in lowered))
        score = float(len(hits))
        if score > best_score:
            best, best_score, best_hits = cat, score, hits
    if best is None:
        other = next((c for c in categories if c.name.lower() == "other"), None)
        return other, 0.3, "No category keywords matched, so the general category is suggested."
    confidence = min(0.95, 0.45 + 0.15 * best_score)
    return best, confidence, f"Matched keywords: {', '.join(best_hits[:5])}."


def suggest_priority(text: str) -> tuple[Priority, float, str]:
    lowered = text.lower()
    crit = [c for c in CRITICAL_CUES if c in lowered]
    high = [c for c in HIGH_CUES if c in lowered]
    low = [c for c in LOW_CUES if c in lowered]
    if crit:
        return Priority.CRITICAL, 0.7, f"Signals of wide impact or security risk: {', '.join(crit[:3])}."
    if high:
        return Priority.HIGH, 0.65, f"The requester appears blocked from working: {', '.join(high[:3])}."
    if low:
        return Priority.LOW, 0.55, f"Reads as a routine request rather than an outage: {', '.join(low[:3])}."
    return Priority.MEDIUM, 0.4, "No urgency signals found, so the standard priority is suggested."


def first_sentence(text: str, limit: int = 220) -> str:
    text = " ".join(text.split())
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    s = m.group(1) if m else text
    return s if len(s) <= limit else s[: limit - 1] + "…"


def summarize(title: str, description: str, status_label: str, messages: list[tuple[str, bool, str]]) -> dict:
    """messages: (author label, is_staff, body). Extractive summary of the issue and latest exchange."""
    points = [f"Issue: {first_sentence(description)}"]
    from_user = [m for m in messages if not m[1]]
    from_staff = [m for m in messages if m[1]]
    if from_user:
        points.append(f"Latest from the requester: {first_sentence(from_user[-1][2])}")
    if from_staff:
        points.append(f"Latest from support: {first_sentence(from_staff[-1][2])}")
    waiting_on = "support" if messages and not messages[-1][1] else "the requester" if messages else "support"
    summary = (
        f"“{title}” is {status_label.lower()} with {len(messages)} message{'s' if len(messages) != 1 else ''} "
        f"in the conversation. The last word is from {'the requester' if waiting_on == 'support' else 'support'}."
    )
    next_step = "Reply to the requester's latest message." if waiting_on == "support" else "Wait for the requester to respond, or follow up."
    return {"summary": summary, "key_points": points, "next_step": next_step}


def draft_reply(category: str, status_label: str, last_user_message: str | None) -> str:
    opener = "Thanks for the update." if last_user_message else "Thanks for reaching out."
    body = {
        "hardware": "Could you tell me the device's asset tag and whether anything changed before the problem started (a drop, a spill, an update)? If it's safe to do so, please try a full restart with the charger connected.",
        "software": "Could you share the exact error message (a screenshot is ideal) and the version of the application you're using? Restarting the application and your computer often clears this up, so it's worth trying first.",
        "network": "Could you let me know whether this happens on other networks too (for example a phone hotspot), and roughly when it started? Restarting your router and reconnecting the VPN is a good first check.",
        "account access": "For your security I'll verify a few details before making changes. In the meantime, please make sure you're signing in with your full work email address.",
    }.get(category.lower(), "Could you share any additional details, such as when the issue started and any error messages you've seen?")
    status_line = f"Your ticket is currently {status_label.lower()}, and I'll keep you updated here as things progress."
    return f"Hi {{name}},\n\n{opener} {body}\n\n{status_line}\n\nBest regards,\n{{agent}}"


def answer_question(question: str, articles: Sequence[HelpArticle]) -> dict:
    """Keyword retrieval over the approved help articles."""
    q = set(words(question))
    if not q:
        return {
            "answer": "Hi! Tell me what's going wrong (for example “I can't connect to the VPN”) and I'll look for a fix.",
            "confident": False, "article_ids": [], "escalate": False,
        }
    scored = []
    for a in articles:
        title_words = set(words(a.title))
        kw = set(words(a.keywords))
        body = set(words(a.body))
        score = 3 * len(q & title_words) + 2 * len(q & kw) + 0.5 * len(q & body)
        scored.append((score, a))
    scored.sort(key=lambda x: (-x[0], x[1].id))
    best_score, best = scored[0] if scored else (0, None)
    if best is None or best_score < 3:
        return {
            "answer": "I couldn't find an approved help article that answers this reliably. The best next step is to "
                      "submit a ticket so a support agent can take a look; I've drafted one for you below.",
            "confident": False, "article_ids": [], "escalate": True,
        }
    steps = best.body.strip()
    return {
        "answer": f"This looks like **{best.title}**. Here's what usually fixes it:\n\n{steps}\n\n"
                  "If that doesn't solve it, submit a ticket and a support agent will help.",
        "confident": True, "article_ids": [best.id], "escalate": False,
    }
