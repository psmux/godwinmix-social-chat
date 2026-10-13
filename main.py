#!/usr/bin/env python3
"""Social Chat for GodwinMix: every platform's live comments in one list.

A service plugin. The core starts one process; it speaks JSON-RPC 2.0 on
stdin and stderr, one object per line, and carries no media. Nothing outside
the Python standard library is imported, so `gmx plugin add` has nothing to
install. Run `python -m unittest discover -s tests` to test it with no core.
"""
import json
import os
import sys
import threading

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from social_chat import panel_files, rpc, tools  # noqa: E402
from social_chat.service import Chat  # noqa: E402

NAME = "social-chat"
VERSION = "1.0.0"
API = 1


def provides():
    return [
        {"kind": "service", "id": "chat", "settings": "schemas/settings.json",
         "skill": "skills/chat/SKILL.md"},
        {"kind": "panel", "id": "panel",
         "panel": {"kind": "iframe", "entry": "ui/panel.html", "slots": ["sidebar"]}},
    ]


def run_tool(chat, rid, params):
    name = str(params.get("name") or "")
    try:
        result = tools.scrub(tools.call(chat, name, params.get("arguments") or {}))
        rpc.reply(rid, {"content": [{"type": "text", "text": _summary(name, result)}],
                        "structuredContent": result})
    except tools.ToolError as e:
        rpc.reply(rid, {"content": [{"type": "text", "text": str(e)}], "isError": True,
                        "structuredContent": {"error": str(e), "data": e.data}})
    except Exception as e:  # a bug: say so, keep serving
        rpc.log("error", "tool %s failed: %s" % (name, tools.redact.text(repr(e))))
        rpc.fail(rid, -32603, "social-chat could not run '%s': %s. The plugin is still "
                 "running; try again, and report it if it repeats." % (name, e),
                 {"tool": name, "retryable": True})


def _summary(name, result):
    if name.endswith("comments"):
        return "%d new comments, %d removed" % (len(result.get("added", [])),
                                               len(result.get("removed", [])))
    return json.dumps(result, ensure_ascii=False)[:2000]


def dispatch(chat, message):
    """Answer one call. Returns False when the process should exit."""
    rid, method = message.get("id"), message.get("method")
    params = message.get("params") or {}
    if method == "tool.call":
        name = str(params.get("name") or "").rsplit("/", 1)[-1]
        if name in tools.SLOW:
            threading.Thread(target=run_tool, args=(chat, rid, params), daemon=True).start()
        else:
            run_tool(chat, rid, params)
    elif method == "health":
        rpc.reply(rid, chat.health())
    elif method == "configure":
        chat.apply(params.get("params", params))
        rpc.reply(rid, {"applied": True})
    elif method in ("start", "stop", "initialized", "configure_log"):
        rpc.reply(rid, {})
    elif method == "shutdown":
        chat.stop()
        rpc.reply(rid, {})
        return False
    elif rid is not None:
        rpc.fail(rid, -32601, "social-chat has no method '%s'. It is a service: it answers "
                 "tool.call, health, configure and shutdown." % method,
                 {"method": method, "retryable": False})
    return True


def show_panel():
    try:
        written = panel_files.mirror(ROOT)
    except OSError as e:
        rpc.log("warn", "could not copy the panel to where the mixer's page looks: %s. "
                "The chat still runs; the panel will not show until it can." % e)
        return
    if written:
        rpc.log("info", "copied %d panel files to %s" % (written, panel_files.target_for(ROOT)))


def main():
    chat = Chat(ROOT)
    rpc.send({"jsonrpc": "2.0", "id": 0, "method": "initialize",
              "params": {"plugin": NAME, "version": VERSION, "api": API,
                         "transports": [], "provides": provides()}})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            rpc.log("debug", "ignored a line on stdin that was not JSON")
            continue
        if message.get("id") == 0 and "result" in message:
            chat.apply(message["result"].get("params") or {})
            rpc.send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
            rpc.log("info", "social-chat ready: %s" % chat.health()["detail"])
            show_panel()
        elif message.get("id") == 0 and "error" in message:
            rpc.log("error", "the core refused the handshake: %s" % message["error"])
            break
        elif "method" in message and not dispatch(chat, message):
            break
    chat.stop()


if __name__ == "__main__":
    main()
