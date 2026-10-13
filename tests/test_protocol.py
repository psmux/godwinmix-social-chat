"""The whole process, driven over stdin and stderr the way the core drives it.

Replays tests/transcript.jsonl: each `core` line is written to the plugin,
and each `plugin` line must turn up on its stderr, in order, as a subset.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from helpers import HERE, ROOT

TIMEOUT_S = 10


def matches(expected, actual):
    if expected == "*":
        return True
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and matches(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        return (isinstance(actual, list) and len(expected) == len(actual)
                and all(matches(e, a) for e, a in zip(expected, actual)))
    return expected == actual


def steps(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for number, raw in enumerate(f, 1):
            line = raw.strip()
            if line and not line.startswith(("#", "//")):
                out.append((number, json.loads(line)))
    return out


class Transcript(unittest.TestCase):
    def test_the_recorded_conversation_replays(self):
        data = tempfile.mkdtemp(prefix="social-chat-transcript-")
        env = dict(os.environ, SOCIAL_CHAT_DATA=data, GMX_PLUGIN="social-chat", GMX_PROVIDE="chat",
                   GMX_INSTANCE="social-chat-chat", GMX_API_LEVEL="1", GMX_PLUGIN_ROOT=ROOT)
        plugin = subprocess.Popen([sys.executable, os.path.join(ROOT, "main.py")], cwd=ROOT, env=env,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        said, done = [], threading.Event()

        def drain():
            for raw in plugin.stderr:
                said.append(raw.decode("utf-8", "replace").strip())
            done.set()

        threading.Thread(target=drain, daemon=True).start()
        at = 0
        for number, step in steps(os.path.join(HERE, "transcript.jsonl")):
            if "core" in step:
                plugin.stdin.write((json.dumps(step["core"]) + "\n").encode())
                plugin.stdin.flush()
                continue
            deadline = time.monotonic() + TIMEOUT_S
            found = False
            while not found and time.monotonic() < deadline:
                if at < len(said):
                    try:
                        found = matches(step["plugin"], json.loads(said[at]))
                    except ValueError:
                        pass
                    at += 1
                elif done.is_set():
                    break
                else:
                    time.sleep(0.01)
            self.assertTrue(found, "line %d never matched. The plugin said:\n%s"
                            % (number, "\n".join(s[:300] for s in said)))
        plugin.stdin.close()
        self.assertEqual(plugin.wait(timeout=8), 0)
        self.assertEqual(plugin.stdout.read(), b"", "a service writes nothing on stdout")
        plugin.stdout.close()
        done.wait(2)
        plugin.stderr.close()


if __name__ == "__main__":
    unittest.main()
