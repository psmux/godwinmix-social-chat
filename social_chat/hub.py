"""Every platform's comments merged into one list, in time order, once each.

Adapters call `add` and `remove` from their own threads; the panel reads with
`changes_since`, which answers what was added and taken away after a sequence
number it already has. That is a few hundred bytes a second on a busy chat,
and nothing at all on a quiet one.

Order is the platform's own timestamp. A platform clock that runs ahead of
ours would put its comments at the bottom for ever, so a time more than a few
seconds in the future is pulled back to when we received it.
"""
import bisect
import threading
from collections import OrderedDict, deque

from .model import now_ms

FUTURE_SLACK_MS = 5000
REMEMBER_IDS = 20000
CHANGE_LOG = 4000


class Hub:
    def __init__(self, keep=500):
        self.keep = max(50, int(keep))
        self.lock = threading.Lock()
        self.seq = 0
        self.epoch = "%x" % int(now_ms())  # a new process is a new list
        self.order = []          # (time, seq, id), sorted
        self.items = {}          # id -> comment
        self.seen = OrderedDict()  # every id ever added, bounded, for dedupe
        self.log = deque(maxlen=CHANGE_LOG)  # (seq, "add" | "remove", id)

    def add(self, item):
        """Add one comment. False when it was seen before."""
        with self.lock:
            if item["id"] in self.seen:
                return False
            self._remember(item["id"])
            received = now_ms()
            if item["time"] > received + FUTURE_SLACK_MS:
                item["time"] = received
            self.seq += 1
            item["seq"] = self.seq
            item["received"] = received
            self.items[item["id"]] = item
            bisect.insort(self.order, (item["time"], self.seq, item["id"]))
            self.log.append((self.seq, "add", item["id"]))
            while len(self.order) > self.keep:
                self._drop(self.order[0][2])
            return True

    def add_many(self, items):
        return sum(1 for item in items if self.add(item))

    def remove(self, comment_id):
        """Take a comment away, as when a platform says it was deleted."""
        with self.lock:
            if comment_id not in self.items:
                return False
            self._drop(comment_id)
            return True

    def remove_where(self, test):
        with self.lock:
            doomed = [cid for cid, item in self.items.items() if test(item)]
            for cid in doomed:
                self._drop(cid)
            return len(doomed)

    def get(self, comment_id):
        with self.lock:
            item = self.items.get(comment_id)
            return dict(item) if item else None

    def snapshot(self):
        with self.lock:
            return [dict(self.items[cid]) for _, _, cid in self.order]

    def changes_since(self, after, limit=300):
        """What changed after `after`. A reader too far behind gets everything."""
        with self.lock:
            oldest = self.log[0][0] if self.log else self.seq + 1
            if after <= 0 or after > self.seq or after < oldest - 1:
                listed = [dict(self.items[cid]) for _, _, cid in self.order][-limit:]
                return {"seq": self.seq, "epoch": self.epoch, "reset": True,
                        "added": listed, "removed": []}
            added, removed = [], []
            for seq, what, cid in self.log:
                if seq <= after:
                    continue
                if what == "add" and cid in self.items:
                    added.append(dict(self.items[cid]))
                elif what == "remove":
                    removed.append(cid)
            return {"seq": self.seq, "epoch": self.epoch, "reset": False,
                    "added": added[-limit:], "removed": removed}

    def _remember(self, comment_id):
        self.seen[comment_id] = True
        while len(self.seen) > REMEMBER_IDS:
            self.seen.popitem(last=False)

    def _drop(self, comment_id):
        item = self.items.pop(comment_id)
        key = (item["time"], item["seq"], comment_id)
        at = bisect.bisect_left(self.order, key)
        if at < len(self.order) and self.order[at] == key:
            del self.order[at]
        self.seq += 1
        self.log.append((self.seq, "remove", comment_id))
