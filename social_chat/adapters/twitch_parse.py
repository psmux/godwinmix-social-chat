"""Twitch chat over IRC: reading the lines, with no network.

The format is IRCv3 with Twitch's tags, documented at
dev.twitch.tv/docs/chat/irc. One line is
`@tag=value;tag=value :prefix COMMAND #channel :text`.
"""
import re

from ..model import comment

_escapes = {"s": " ", ":": ";", "\\": "\\", "r": "\r", "n": "\n"}
_login = re.compile(r"^[a-z0-9_]{2,25}$")


def channels_of(text):
    """`#a, b https://twitch.tv/c` as ["a", "b", "c"], lower case, at most 20."""
    found = []
    for word in re.split(r"[\s,;]+", (text or "").strip().lower()):
        word = word.rstrip("/").rsplit("/", 1)[-1].lstrip("#@")
        if _login.match(word) and word not in found:
            found.append(word)
    return found[:20]


def unescape(value):
    out, i = [], 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            out.append(_escapes.get(value[i + 1], value[i + 1]))
            i += 2
            continue
        if ch != "\\":
            out.append(ch)
        i += 1
    return "".join(out)


def split(line):
    """One IRC line as (tags, prefix, command, params). params[-1] is the text."""
    tags, prefix = {}, ""
    line = line.rstrip("\r\n")
    if line.startswith("@"):
        raw, _, line = line[1:].partition(" ")
        for pair in raw.split(";"):
            key, _, value = pair.partition("=")
            tags[key] = unescape(value)
    if line.startswith(":"):
        prefix, _, line = line[1:].partition(" ")
    head, sep, trailing = line.partition(" :")
    params = head.split()
    command = params.pop(0).upper() if params else ""
    if sep:
        params.append(trailing)
    return tags, prefix, command, params


def read(line):
    """What one line means: ("comment", item), ("delete", id),
    ("clear_user", user id), ("clear_all", channel), ("ping", text),
    ("reconnect", ""), ("notice", text) or (None, None)."""
    tags, prefix, command, params = split(line)
    if command == "PING":
        return "ping", params[-1] if params else "tmi.twitch.tv"
    if command == "RECONNECT":
        return "reconnect", ""
    if command == "PRIVMSG" and len(params) >= 2:
        return "comment", _privmsg(tags, prefix, params)
    if command == "USERNOTICE" and params:
        return "comment", _usernotice(tags, params)
    if command == "CLEARMSG" and tags.get("target-msg-id"):
        return "delete", "twitch:" + tags["target-msg-id"]
    if command == "CLEARCHAT":
        if tags.get("target-user-id"):
            return "clear_user", tags["target-user-id"]
        return "clear_all", params[0].lstrip("#") if params else ""
    if command == "NOTICE":
        return "notice", params[-1] if params else ""
    return None, None


def _privmsg(tags, prefix, params):
    channel = params[0].lstrip("#")
    text = params[-1]
    if text.startswith("\x01ACTION ") and text.endswith("\x01"):
        text = text[8:-1]
    login = prefix.split("!", 1)[0]
    kind = "superchat" if tags.get("bits") else "chat"
    return comment(
        "twitch", tags.get("id") or "%s-%s" % (login, tags.get("tmi-sent-ts", "")),
        tags.get("display-name") or login, text, tags.get("tmi-sent-ts"),
        author_id=tags.get("user-id") or login, channel=channel,
        colour=tags.get("color"), badges=_badges(tags), kind=kind,
        amount=("%s bits" % tags["bits"]) if tags.get("bits") else None,
        url="https://www.twitch.tv/" + login if login else None)


def _usernotice(tags, params):
    said = params[1] if len(params) > 1 else ""
    system = tags.get("system-msg", "")
    text = ("%s %s" % (system, said)).strip() if said else system
    return comment(
        "twitch", tags.get("id") or "notice-" + tags.get("tmi-sent-ts", ""),
        tags.get("display-name") or tags.get("login"), text, tags.get("tmi-sent-ts"),
        author_id=tags.get("user-id"), channel=params[0].lstrip("#"),
        colour=tags.get("color"), badges=_badges(tags), kind="member")


def _badges(tags):
    names = {"broadcaster": "owner", "moderator": "moderator", "subscriber": "member",
             "vip": "vip", "partner": "verified"}
    found = []
    for badge in (tags.get("badges") or "").split(","):
        name = badge.split("/", 1)[0]
        if name in names:
            found.append(names[name])
    return found
