"""Keep keys and tokens out of everything this plugin says.

Every secret the settings hold is registered here, and every line that leaves
the process (a log line, a status, a tool answer) goes through `text`. A
platform error that echoes a URL with `access_token=` in it cannot leak the
token that way either.
"""
import re
import threading

_lock = threading.Lock()
_values = set()
_query = re.compile(r"((?:access_token|key|token|client_secret)=)[^&\s\"']+", re.I)


def register(value):
    if value and len(value) >= 6:
        with _lock:
            _values.add(value)


def forget_all():
    with _lock:
        _values.clear()


def text(value):
    if not isinstance(value, str):
        return value
    with _lock:
        known = sorted(_values, key=len, reverse=True)
    for secret in known:
        if secret in value:
            value = value.replace(secret, "[hidden]")
    return _query.sub(r"\1[hidden]", value)


def mask(value):
    """How a stored secret is shown back: never whole, the last four at most."""
    if not value:
        return ""
    if len(value) <= 8:
        return "stored"
    return "stored, ending " + value[-4:]
