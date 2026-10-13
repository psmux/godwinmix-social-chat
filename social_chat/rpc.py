"""The control channel: JSON-RPC 2.0, one object per line.

The core writes to our stdin and reads our stderr. stdout is never used: a
service carries no media, and keeping stdout quiet means a stray print cannot
be mistaken for anything. Every write goes through one lock because the
adapters log from their own threads.
"""
import json
import sys
import threading

_lock = threading.Lock()
_out = sys.stderr


def use_stream(stream):
    """Send to another stream. The tests use this to capture what is said."""
    global _out
    _out = stream


def send(obj):
    line = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    with _lock:
        _out.write(line + "\n")
        _out.flush()


def log(level, message):
    send({"jsonrpc": "2.0", "method": "log",
          "params": {"level": level, "message": message}})


def notify(method, params):
    send({"jsonrpc": "2.0", "method": method, "params": params})


def reply(rid, result):
    if rid is not None:
        send({"jsonrpc": "2.0", "id": rid, "result": result})


def fail(rid, code, message, data=None):
    if rid is None:
        return
    body = {"code": code, "message": message, "data": data or {}}
    send({"jsonrpc": "2.0", "id": rid, "error": body})
