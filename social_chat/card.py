"""The words for the on air graphic: a comment cut into a template's fields.

The SVG templates never wrap, so the words are wrapped here, at word
boundaries, into as many lines as the template has. Each line also carries
`data-fit-width` in the template, so a line of wide letters shrinks rather
than running off the panel.
"""
import base64
import os
import re

STYLES = {"card": ("comment-card.svg", 3, 42), "strap": ("comment-strap.svg", 1, 90)}
PLATFORM_COLOURS = {"youtube": "#ff0033", "twitch": "#9146ff", "facebook": "#1877f2",
                    "webhook": "#10b981", "x": "#71767b", "practice": "#f59e0b"}
PLATFORM_NAMES = {"youtube": "YOUTUBE", "twitch": "TWITCH", "facebook": "FACEBOOK",
                  "webhook": "WEBHOOK", "x": "X"}
CLEAR_PIXEL = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAA"
               "DUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
MAX_FIELD = 2000


def wrap(text, lines, width):
    """At most `lines` lines of about `width` characters, the last one ending
    in an ellipsis when the words did not all fit."""
    words = re.sub(r"\s+", " ", text or "").strip().split(" ")
    out, current = [], ""
    for word in words:
        while len(word) > width:  # one long word (a link, a laugh) is cut
            word = word[:width - 1] + "…"
        trial = (current + " " + word).strip()
        if len(trial) <= width:
            current = trial
            continue
        out.append(current)
        current = word
        if len(out) == lines:
            break
    else:
        out.append(current)
        current = None
    if current is not None and out:
        out[-1] = out[-1].rstrip(" .,;:") + "…"
    out = [line for line in out if line][:lines]
    return out + [""] * (lines - len(out))


def initials(name):
    parts = [p for p in re.split(r"[\s_.\-]+", name or "") if p]
    letters = "".join(p[0] for p in parts[:2]).upper()
    return letters or "?"


def fields(item, style, avatar_uri=None):
    """The template's fields for one comment."""
    _, lines, width = STYLES.get(style, STYLES["card"])
    platform = item.get("platform", "")
    tag = item.get("amount") or ("QUESTION" if item.get("question") else "")
    out = {
        "author": item.get("author", ""),
        "platform": PLATFORM_NAMES.get(platform, platform.upper()[:16]),
        "platform_colour": PLATFORM_COLOURS.get(platform, "#64748b"),
        "tag": tag,
    }
    if style == "strap":
        out["message"] = wrap(item.get("text", ""), 1, width)[0]
    else:
        for n, line in enumerate(wrap(item.get("text", ""), lines, width), 1):
            out["line%d" % n] = line
        out["initials"] = initials(item.get("author"))
        good = avatar_uri if avatar_uri and len(avatar_uri) <= MAX_FIELD else None
        out["avatar"] = good or CLEAR_PIXEL
    return out


def source_id(style):
    """The mixer source (and scene item) a style is drawn by."""
    return "social-chat-" + (style if style in STYLES else "card")


def template_uri(root, style):
    """The `template:` address of a style's SVG, by absolute path."""
    name = STYLES.get(style, STYLES["card"])[0]
    path = os.path.abspath(os.path.join(root, "graphics", name)).replace("\\", "/")
    return "template:" + path


def data_uri(kind, data):
    return "data:%s;base64,%s" % (kind, base64.b64encode(data).decode("ascii"))
