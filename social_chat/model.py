"""One comment, the same shape whichever platform it came from.

Every adapter turns what its platform sends into a call to `comment()`, and
nothing downstream knows which platform a comment came from except by reading
its `platform` field. Times are milliseconds since the epoch, as floats.
"""
import re
import time
from datetime import datetime, timezone

MAX_TEXT = 2000
MAX_NAME = 120

QUESTION_WORDS = (
    "who", "what", "when", "where", "why", "how", "which", "whose", "can",
    "could", "would", "should", "will", "is", "are", "do", "does", "did",
    "have", "has", "any", "anyone",
)
_question_start = re.compile(r"^\s*(q\s*[:.)-]|(%s)\b)" % "|".join(QUESTION_WORDS),
                             re.IGNORECASE)


def now_ms():
    return time.time() * 1000.0


def parse_time(value, fallback=None):
    """An ISO 8601 string, epoch seconds or epoch milliseconds, as epoch ms."""
    if value is None or value == "":
        return fallback if fallback is not None else now_ms()
    if isinstance(value, (int, float)):
        number = float(value)
        return number * 1000.0 if number < 1e11 else number
    text = str(value).strip()
    if text.isdigit():
        return parse_time(int(text), fallback)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    if re.search(r"[+-]\d{4}$", text):
        text = text[:-2] + ":" + text[-2:]
    text = re.sub(r"(\.\d{6})\d+", r"\1", text)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return fallback if fallback is not None else now_ms()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp() * 1000.0


def is_question(text):
    """A comment reads as a question when it asks one, in English at least."""
    if not text:
        return False
    if "?" in text or "？" in text:
        return True
    return bool(_question_start.match(text)) and len(text.split()) >= 3


def clean(text, limit):
    text = "" if text is None else str(text)
    text = "".join(ch if ch >= " " or ch == "\t" else " " for ch in text)
    return text.strip()[:limit]


def comment(platform, native_id, author, text, when=None, **extra):
    """Build one comment. `native_id` is the platform's own id for it."""
    body = clean(text, MAX_TEXT)
    item = {
        "id": "%s:%s" % (platform, native_id),
        "platform": platform,
        "author": clean(author, MAX_NAME) or "someone",
        "text": body,
        "time": parse_time(when),
        "kind": extra.pop("kind", "chat"),
        "question": is_question(body),
    }
    for key in ("author_id", "avatar", "channel", "colour", "amount", "url"):
        value = extra.pop(key, None)
        if value not in (None, ""):
            item[key] = clean(value, 400)
    badges = extra.pop("badges", None)
    if badges:
        item["badges"] = sorted(set(badges))
    return item
