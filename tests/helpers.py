"""Shared bits for the tests: where the fixtures are, and a sink that records."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)


def fixture(name):
    path = os.path.join(HERE, "fixtures", name)
    if name.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    with open(path, "rb") as f:
        return f.read()


class Sink:
    """What an adapter writes to, kept in lists."""

    def __init__(self):
        self.added, self.removed, self.wheres = [], [], []

    def add(self, item):
        if any(a["id"] == item["id"] for a in self.added):
            return False
        self.added.append(item)
        return True

    def remove(self, comment_id):
        self.removed.append(comment_id)
        return True

    def remove_where(self, test):
        self.wheres.append(test)
        return 0
