"""The service: settings, the merged list, the moderation and the adapters.

One of these per process. The protocol loop in main.py hands it the
handshake's params and every tool call; it starts an adapter for each
platform that is set up, and restarts only the adapters whose settings
changed.
"""
import os
import threading

from . import redact
from .adapters import ADAPTERS
from .adapters.base import OFF
from .avatars import Avatars
from .hub import Hub
from .moderation import Moderation
from .settings import Settings


class Sink:
    """What adapters write to: the hub, with banned authors kept out."""

    def __init__(self, chat):
        self.chat = chat

    def add(self, item):
        if self.chat.moderation.is_banned(item):
            return False
        return self.chat.hub.add(item)

    def remove(self, comment_id):
        return self.chat.hub.remove(comment_id)

    def remove_where(self, test):
        return self.chat.hub.remove_where(test)


class Chat:
    def __init__(self, root, folder=None):
        self.root = root
        self.settings = Settings(folder)
        self.hub = Hub(self.settings.values["keep"])
        self.moderation = Moderation(self.settings.folder)
        self.avatars = Avatars()
        self.sink = Sink(self)
        self.lock = threading.Lock()
        self.running = {}   # platform -> adapter
        self.onair = None   # {"id", "style", "comment"} while a card is up

    # -- adapters ----------------------------------------------------------------

    def apply(self, params=None):
        """Take the mixer's params and start what is set up."""
        self.settings.take_mixer(params or {})
        self.restart([cls.platform for cls in ADAPTERS])

    def restart(self, platforms):
        values = self.settings.values
        with self.lock:
            for cls in ADAPTERS:
                if cls.platform not in platforms:
                    continue
                old = self.running.pop(cls.platform, None)
                if old is not None:
                    old.stop()
                if cls.configured(values):
                    adapter = cls(dict(values), self.sink)
                    self.running[cls.platform] = adapter
                    adapter.start()

    def stop(self):
        with self.lock:
            for adapter in self.running.values():
                adapter.stop()
            self.running.clear()

    def statuses(self):
        with self.lock:
            running = dict(self.running)
        out = []
        for cls in ADAPTERS:
            if cls.platform in running:
                view = running[cls.platform].view()
            else:
                view = {"platform": cls.platform, "title": cls.title, "state": OFF,
                        "detail": "not set up", "next": _setup_hint(cls.platform),
                        "count": 0}
            out.append({k: redact.text(v) for k, v in view.items()})
        return out

    def save_settings(self, values):
        changed = self.settings.update(values)
        if "keep" in changed:
            self.hub.keep = max(50, int(self.settings.values["keep"]))
        touched = [cls.platform for cls in ADAPTERS
                   if any(key.startswith(cls.platform + "_") for key in changed)]
        self.restart(touched)
        return changed

    def health(self):
        states = [s for s in self.statuses() if s["state"] != OFF]
        failing = [s for s in states if s["state"] in ("failing", "unavailable")]
        words = "; ".join("%s %s" % (s["title"], s["state"]) for s in states)
        return {"state": "degraded" if failing else "ok",
                "detail": words or "no platform is set up yet"}

    def template_root(self):
        return os.path.abspath(self.root)


def _setup_hint(platform):
    return {
        "youtube": "Add a YouTube API key and the stream's address in Settings.",
        "twitch": "Type a Twitch channel name in Settings. No account is needed.",
        "facebook": "Paste a Facebook Page access token in Settings.",
        "webhook": "Switch the webhook on in Settings to accept comments by POST.",
        "x": "X needs a paid API plan; see the README.",
        "practice": "Switch practice mode on to rehearse with made up comments.",
    }.get(platform, "")
