"""The generic webhook: what any platform or relay may POST, read with no network.

One comment, a list of them, or `{"comments": [...]}`. Each is an object
with at least the words and who wrote them, under any of the common names:

    {"platform": "tiktok", "id": "7301", "author": "Sam", "text": "hello",
     "time": "2026-10-13T18:00:00Z", "avatar": "https://..."}

docs/webhook.md lists every name read. Something with no words is skipped
and counted, never an error for the whole request.
"""
import hashlib
import re

from ..model import comment

MAX_PER_REQUEST = 200

ALIASES = {
    "text": ("text", "message", "comment", "content", "body", "msg"),
    "author": ("author", "user", "username", "user_name", "display_name", "name", "nick"),
    "id": ("id", "message_id", "comment_id", "msg_id", "uuid"),
    "time": ("time", "timestamp", "created_at", "created_time", "published_at", "ts"),
    "avatar": ("avatar", "avatar_url", "picture", "profile_image_url", "image"),
    "author_id": ("author_id", "user_id", "userid", "uid"),
    "platform": ("platform", "source", "service", "network"),
}


def _first(obj, field):
    for key in ALIASES[field]:
        value = obj.get(key)
        if isinstance(value, dict):  # {"user": {"name": ...}} and the like
            value = value.get("name") or value.get("display_name") or value.get("url")
        if value not in (None, ""):
            return value
    return None


def platform_of(value):
    slug = re.sub(r"[^a-z0-9-]+", "-", str(value or "webhook").lower()).strip("-")
    return slug[:24] or "webhook"


def one(obj):
    if not isinstance(obj, dict):
        return None
    text = _first(obj, "text")
    if text is None or not str(text).strip():
        return None
    author = _first(obj, "author") or "someone"
    platform = platform_of(_first(obj, "platform"))
    native = _first(obj, "id")
    when = _first(obj, "time")
    if native is None:
        # No id: the same words from the same person at the same moment are
        # the same comment, so a relay that posts twice is still read once.
        key = "%s|%s|%s|%s" % (platform, author, text, when)
        native = "h" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    avatar = _first(obj, "avatar")
    if avatar and not str(avatar).startswith(("https://", "http://")):
        avatar = None
    return comment(platform, native, author, text, when,
                   author_id=_first(obj, "author_id"), avatar=avatar,
                   amount=obj.get("amount"), url=obj.get("url"),
                   kind=obj.get("kind") if obj.get("kind") in ("chat", "superchat",
                                                               "member", "event") else "chat")


def items(payload):
    """(comments, skipped) from one request's JSON."""
    if isinstance(payload, dict) and isinstance(payload.get("comments"), list):
        payload = payload["comments"]
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return [], 1
    read = [one(obj) for obj in payload[:MAX_PER_REQUEST]]
    found = [c for c in read if c]
    return found, len(payload) - len(found)
