"""Facebook Graph API: reading live video comments, with no network.

Two shapes, both from developers.facebook.com/docs/live-video-api: the
`live_comments` event stream sends one comment object per event, and the
`comments` edge answers `{data: [...], paging: {...}}`. A comment object is
`{id, message, created_time, from: {id, name, picture}}`; `from` is left out
when the Page's token may not see who wrote it.
"""
import json
import re

from ..model import comment

_video_in_url = re.compile(r"(?:/videos/(?:[^/?#]+/)?|[?&]v=|/live_videos?/)(\d{6,})")
_bare = re.compile(r"^\d{6,}$")


def video_of(text):
    """A live video or video id out of what the operator pasted, or ''."""
    text = (text or "").strip()
    if _bare.match(text):
        return text
    found = _video_in_url.search(text)
    return found.group(1) if found else ""


def one(obj, video=""):
    """One Graph comment object as a comment, or None when it has no words."""
    if not isinstance(obj, dict) or not obj.get("id"):
        return None
    words = obj.get("message") or ""
    if not words.strip():
        return None
    who = obj.get("from") or {}
    picture = ((who.get("picture") or {}).get("data") or {}).get("url")
    return comment("facebook", obj["id"], who.get("name") or "Facebook user", words,
                   obj.get("created_time"), author_id=who.get("id"), avatar=picture,
                   channel=video)


def page(payload, video=""):
    """A `comments` edge answer, oldest first."""
    found = [one(obj, video) for obj in payload.get("data") or []]
    found = [c for c in found if c]
    found.sort(key=lambda c: c["time"])
    return found


def event(data, video=""):
    """One `live_comments` event's data line."""
    try:
        return one(json.loads(data), video)
    except ValueError:
        return None


def live_video(payload):
    """(id, title) of the first live video in a `live_videos` answer."""
    for item in payload.get("data") or []:
        if item.get("id") and item.get("status", "LIVE") == "LIVE":
            return item["id"], item.get("title") or item.get("description") or ""
    return None, ""


def error_of(body):
    """(code, message) from a Graph error body."""
    error = body.get("error") or {}
    return int(error.get("code") or 0), error.get("message", "")
