"""YouTube Data API v3: reading what the live chat endpoints answer.

Pure functions, no network, so the tests feed them the documented payloads.
The shapes are from developers.google.com/youtube/v3/live/docs/liveChatMessages.
"""
import re

from ..model import comment

_video = re.compile(r"(?:v=|youtu\.be/|/live/|/shorts/|/embed/|/video/)([A-Za-z0-9_-]{11})")
_bare_video = re.compile(r"^[A-Za-z0-9_-]{11}$")
_channel = re.compile(r"(UC[A-Za-z0-9_-]{22})")
_handle = re.compile(r"(?:^|/)(@[A-Za-z0-9._-]{3,30})")


def target_of(text):
    """What the operator pasted: ("video", id), ("channel", id), ("handle", @x) or ("mine", "")."""
    text = (text or "").strip()
    if not text:
        return ("mine", "")
    found = _video.search(text)
    if found:
        return ("video", found.group(1))
    if _bare_video.match(text):
        return ("video", text)
    found = _channel.search(text)
    if found:
        return ("channel", found.group(1))
    found = _handle.search(text)
    if found:
        return ("handle", found.group(1))
    if re.match(r"^[A-Za-z0-9._-]{3,30}$", text):
        return ("handle", "@" + text)
    return ("unknown", text)


def chat_id_of_video(payload):
    """(live chat id or None, the video's title) from a videos.list answer."""
    items = payload.get("items") or []
    if not items:
        return None, ""
    details = items[0].get("liveStreamingDetails") or {}
    title = (items[0].get("snippet") or {}).get("title", "")
    return details.get("activeLiveChatId"), title


def first_id(payload):
    """The first item's id from channels.list or search.list."""
    for item in payload.get("items") or []:
        ident = item.get("id")
        if isinstance(ident, dict):
            ident = ident.get("videoId") or ident.get("channelId")
        if ident:
            return ident
    return None


def chat_id_of_broadcasts(payload):
    for item in payload.get("items") or []:
        chat = (item.get("snippet") or {}).get("liveChatId")
        if chat:
            return chat, (item.get("snippet") or {}).get("title", "")
    return None, ""


def messages(payload, channel=""):
    """Read one liveChatMessages.list answer.

    Answers a dict: comments, deleted (ids), banned (author ids), ended,
    next_page and interval_ms.
    """
    out = {"comments": [], "deleted": [], "banned": [], "ended": False,
           "next_page": payload.get("nextPageToken"),
           "interval_ms": int(payload.get("pollingIntervalMillis") or 5000)}
    if payload.get("offlineAt"):
        out["ended"] = True
    for item in payload.get("items") or []:
        _read_item(item, channel, out)
    return out


def _read_item(item, channel, out):
    snippet = item.get("snippet") or {}
    kind = snippet.get("type", "")
    if kind == "messageDeletedEvent":
        gone = (snippet.get("messageDeletedDetails") or {}).get("deletedMessageId")
        if gone:
            out["deleted"].append("youtube:" + gone)
        return
    if kind == "userBannedEvent":
        who = ((snippet.get("userBannedDetails") or {}).get("bannedUserDetails") or {})
        if who.get("channelId"):
            out["banned"].append(who["channelId"])
        return
    if kind == "chatEndedEvent":
        out["ended"] = True
        return
    text, extra = _text_of(kind, snippet)
    if text is None:
        return
    author = item.get("authorDetails") or {}
    out["comments"].append(comment(
        "youtube", item.get("id", ""), author.get("displayName"), text,
        snippet.get("publishedAt"), author_id=author.get("channelId"),
        avatar=author.get("profileImageUrl"), channel=channel,
        badges=_badges(author), url=author.get("channelUrl"), **extra))


def _text_of(kind, snippet):
    """The words of one message, and what else it says, by its type."""
    if kind == "textMessageEvent":
        details = snippet.get("textMessageDetails") or {}
        return details.get("messageText") or snippet.get("displayMessage", ""), {}
    if kind == "superChatEvent":
        details = snippet.get("superChatDetails") or {}
        words = details.get("userComment") or snippet.get("displayMessage", "")
        return words, {"kind": "superchat", "amount": details.get("amountDisplayString")}
    if kind == "superStickerEvent":
        details = snippet.get("superStickerDetails") or {}
        alt = (details.get("superStickerMetadata") or {}).get("altText", "a Super Sticker")
        return alt, {"kind": "superchat", "amount": details.get("amountDisplayString")}
    if kind in ("newSponsorEvent", "memberMilestoneChatEvent", "membershipGiftingEvent",
                "giftMembershipReceivedEvent"):
        details = snippet.get("memberMilestoneChatDetails") or {}
        words = details.get("userComment") or snippet.get("displayMessage", "")
        return words, {"kind": "member"}
    if snippet.get("hasDisplayContent") and snippet.get("displayMessage"):
        return snippet["displayMessage"], {"kind": "event"}
    return None, {}


def _badges(author):
    pairs = (("isChatOwner", "owner"), ("isChatModerator", "moderator"),
             ("isChatSponsor", "member"), ("isVerified", "verified"))
    return [name for key, name in pairs if author.get(key)]


def error_reason(body):
    """The first `reason` in a Google API error body, and its message."""
    error = body.get("error") or {}
    reasons = [e.get("reason", "") for e in error.get("errors") or []]
    status = error.get("status", "")
    return (reasons[0] if reasons else status), error.get("message", "")
