"""HTTP from the standard library: a JSON GET and an event stream reader.

Every request has a timeout, because an adapter thread waiting for ever on a
dead connection is an adapter that never reconnects.
"""
import json
import ssl
import urllib.error
import urllib.request

USER_AGENT = "godwinmix-social-chat/1.0 (+https://github.com/psmux/godwinmix-social-chat)"
_context = ssl.create_default_context()


class HttpError(Exception):
    """A response that was not 2xx, with its parsed body when it had one."""

    def __init__(self, status, body):
        super().__init__("HTTP %d" % status)
        self.status = status
        self.body = body if isinstance(body, dict) else {}


def get_json(url, headers=None, timeout=15):
    request = urllib.request.Request(url, headers=dict(headers or {}, **{
        "User-Agent": USER_AGENT, "Accept": "application/json"}))
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_context) as answer:
            return json.loads(answer.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, _body_of(e)) from None


def open_stream(url, headers=None, timeout=60):
    """Open a text/event-stream. Read lines from the answer with readline."""
    request = urllib.request.Request(url, headers=dict(headers or {}, **{
        "User-Agent": USER_AGENT, "Accept": "text/event-stream"}))
    try:
        return urllib.request.urlopen(request, timeout=timeout, context=_context)
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, _body_of(e)) from None


def get_bytes(url, limit=200_000, timeout=10):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout, context=_context) as answer:
        kind = answer.headers.get("Content-Type", "application/octet-stream")
        return kind.split(";")[0].strip(), answer.read(limit + 1)


def events(stream):
    """Yield the `data` of each server sent event, joined when it spans lines."""
    data = []
    for raw in stream:
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if not line:
            if data:
                yield "\n".join(data)
                data = []
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        if field == "data":
            data.append(value[1:] if value.startswith(" ") else value)
    if data:
        yield "\n".join(data)


def _body_of(error):
    try:
        return json.loads(error.read().decode("utf-8"))
    except Exception:
        return {}
