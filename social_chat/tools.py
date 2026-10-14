"""The plugin's tools: what the panel calls, and what an agent sees over MCP.

Each tool takes the arguments object and answers a plain dict, which main.py
wraps in MCP's `{content, structuredContent}`. A tool that needs the network
(fetching pictures) is marked SLOW and runs off the protocol thread, so
`health` is never kept waiting.
"""
from . import card, redact
from .adapters import webhook_parse
from .moderation import author_key
from .settings import SettingsError
from . import seal


# The core gives a tool five seconds to answer; a long poll leaves room.
MAX_WAIT_MS = 3500


class ToolError(Exception):
    def __init__(self, message, data=None):
        super().__init__(message)
        self.data = data or {}


def _comment(chat, args):
    cid = str(args.get("id") or "")
    item = chat.hub.get(cid) or chat.moderation.pins.get(cid)
    if not item:
        raise ToolError("there is no comment '%s' in the list (it may have scrolled off "
                        "the end). Call comments to see what is there." % cid,
                        {"id": cid})
    return item


def comments(chat, args):
    after = int(args.get("after") or 0)
    if args.get("epoch") and args["epoch"] != chat.hub.epoch:
        after = 0
    wait_ms = min(max(int(args.get("wait_ms") or 0), 0), MAX_WAIT_MS)
    chat.hub.wait(after, wait_ms / 1000.0)
    answer = chat.hub.changes_since(after, int(args.get("limit") or 300))
    answer["statuses"] = chat.statuses()
    answer["moderation"] = chat.moderation.view()
    answer["onair"] = chat.onair
    answer["question_colour"] = chat.settings.values["question_colour"]
    answer["card_style"] = chat.settings.values["card_style"]
    return answer


def status(chat, args):
    return {"statuses": chat.statuses(), "data_folder": chat.settings.folder,
            "comments": len(chat.hub.items), "onair": chat.onair,
            "templates": {s: card.template_uri(chat.root, s) for s in card.STYLES}}


def settings(chat, args):
    return {"settings": chat.settings.view(), "statuses": chat.statuses(),
            "seal_key": seal.public_hex()}


def save_settings(chat, args):
    values = args.get("values")
    if not isinstance(values, dict):
        raise ToolError("save_settings takes {values: {...}} with the keys to change")
    try:
        changed = chat.save_settings(values)
    except SettingsError as e:
        raise ToolError(str(e), {"retryable": False}) from None
    return {"changed": changed, "settings": chat.settings.view(),
            "statuses": chat.statuses()}


def reconnect(chat, args):
    platform = args.get("platform")
    chat.restart([platform] if platform else [s["platform"] for s in chat.statuses()])
    return {"statuses": chat.statuses()}


def pin(chat, args):
    item = _comment(chat, args)
    chat.moderation.pin(item, bool(args.get("pinned", True)))
    return chat.moderation.view()


def hide(chat, args):
    item = _comment(chat, args)
    chat.moderation.hide(item["id"], bool(args.get("hidden", True)))
    return chat.moderation.view()


def ban(chat, args):
    banned = bool(args.get("banned", True))
    if args.get("key") and not banned:
        chat.moderation.unban_key(args["key"])
        return chat.moderation.view()
    item = _comment(chat, args)
    key = chat.moderation.ban(item, banned)
    if banned:
        chat.hub.remove_where(lambda c: author_key(c) == key)
    return chat.moderation.view()


def card_fields(chat, args):
    """The fields and template for one comment, and mark it as on air."""
    item = _comment(chat, args)
    style = args.get("style") or chat.settings.values["card_style"]
    if style not in card.STYLES:
        raise ToolError("style is 'card' or 'strap', not '%s'" % style, {"style": style})
    avatar = chat.avatars.get(item.get("avatar"), 40) if style == "card" else ""
    chat.onair = {"id": item["id"], "style": style, "comment": item}
    return {"source": card.source_id(style), "uri": card.template_uri(chat.root, style),
            "style": style, "fields": card.fields(item, style, avatar), "comment": item}


def card_off(chat, args):
    chat.onair = None
    return {"onair": None}


def avatars(chat, args):
    urls = [u for u in args.get("urls") or [] if isinstance(u, str)]
    return {"avatars": chat.avatars.many(urls)}


def test_comment(chat, args):
    """Put one comment in the list by hand, as if the webhook had received it."""
    item = webhook_parse.one({"platform": args.get("platform") or "webhook",
                              "author": args.get("author") or "Test",
                              "text": args.get("text") or "Testing, one two three",
                              "id": args.get("id")})
    if not item:
        raise ToolError("test_comment needs some text")
    item["via"] = "webhook"
    chat.sink.add(item)
    return {"comment": item}


TOOLS = {f.__name__: f for f in (comments, status, settings, save_settings, reconnect, pin,
                                 hide, ban, card_fields, card_off, avatars, test_comment)}
SLOW = {"card_fields", "avatars", "save_settings", "reconnect", "comments"}


def call(chat, name, args):
    tool = TOOLS.get(name.rsplit("/", 1)[-1])
    if tool is None:
        raise ToolError("social-chat has no tool '%s'. It has: %s."
                        % (name, ", ".join(sorted(TOOLS))), {"tools": sorted(TOOLS)})
    return tool(chat, args if isinstance(args, dict) else {})


def scrub(value):
    """Every string in an answer, with secrets taken out."""
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return redact.text(value)
