"""Pins, hidden comments and banned authors. Local only.

Nothing here reaches a platform: banning an author here hides them in this
mixer and nowhere else. Bans are kept in `moderation.json` beside the
settings so they survive a restart; pins and hidden comments belong to one
show and are kept in memory.
"""
import json
import os
import threading

MAX_PINS = 20


def author_key(item):
    """Who wrote a comment, as `platform:author id`, falling back to the name."""
    who = item.get("author_id") or ("name:" + item.get("author", "").lower())
    return "%s:%s" % (item.get("platform", ""), who)


class Moderation:
    def __init__(self, folder):
        self.path = os.path.join(folder, "moderation.json")
        self.lock = threading.Lock()
        self.pins = {}      # id -> the comment, so a pin outlives the list
        self.hidden = set()
        self.banned = {}    # author key -> {"author", "platform"}
        self.version = 0
        self._read()

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                self.banned = json.load(f).get("banned") or {}
        except (OSError, ValueError):
            self.banned = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"banned": self.banned}, f, indent=2, sort_keys=True)

    def pin(self, item, pinned=True):
        with self.lock:
            if pinned:
                self.pins[item["id"]] = dict(item)
                while len(self.pins) > MAX_PINS:
                    self.pins.pop(next(iter(self.pins)))
            else:
                self.pins.pop(item["id"], None)
            self.version += 1

    def hide(self, comment_id, hidden=True):
        with self.lock:
            (self.hidden.add if hidden else self.hidden.discard)(comment_id)
            self.version += 1

    def ban(self, item, banned=True):
        key = author_key(item)
        with self.lock:
            if banned:
                self.banned[key] = {"author": item.get("author", ""),
                                    "platform": item.get("platform", "")}
            else:
                self.banned.pop(key, None)
            self.version += 1
            self._save()
        return key

    def unban_key(self, key):
        with self.lock:
            self.banned.pop(key, None)
            self.version += 1
            self._save()

    def is_banned(self, item):
        return author_key(item) in self.banned

    def view(self):
        with self.lock:
            return {"version": self.version, "pins": list(self.pins.values()),
                    "hidden": sorted(self.hidden),
                    "banned": [dict(v, key=k) for k, v in sorted(self.banned.items())]}
