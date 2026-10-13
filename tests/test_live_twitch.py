"""A real check against Twitch: anonymous read needs no credentials.

Skipped unless SOCIAL_CHAT_LIVE=1, because it needs the internet and a busy
channel that is live right now. It joins a list of usually busy channels for
30 seconds and passes when comments arrive from any of them.

    SOCIAL_CHAT_LIVE=1 python -m unittest tests/test_live_twitch.py
"""
import os
import time
import unittest

import helpers  # noqa: F401
from social_chat.adapters.twitch import Twitch
from social_chat.hub import Hub

BUSY = ("kaicenat, xqc, ibai, jynxzi, caseoh_, zackrawrr, hasanabi, summit1g, tarik, shroud, "
        "loltyler1, papaplatte, gaules, eslcs, riotgames, lirik, auronplay, rubius, ohnepixel, squeex")
SECONDS = int(os.environ.get("SOCIAL_CHAT_LIVE_SECONDS", "30"))


@unittest.skipUnless(os.environ.get("SOCIAL_CHAT_LIVE") == "1", "set SOCIAL_CHAT_LIVE=1 to talk to Twitch")
class LiveTwitch(unittest.TestCase):
    def test_comments_arrive_from_a_busy_public_channel(self):
        hub = Hub(keep=5000)
        adapter = Twitch({"twitch_channels": os.environ.get("SOCIAL_CHAT_LIVE_CHANNELS", BUSY)}, hub)
        adapter.start()
        started = time.monotonic()
        try:
            while time.monotonic() - started < SECONDS:
                time.sleep(1)
        finally:
            adapter.stop()
        found = hub.snapshot()
        channels = sorted({c.get("channel") for c in found})
        print("\n%d comments in %d s from %d channels: %s. State: %s"
              % (len(found), SECONDS, len(channels), ", ".join(channels), adapter.view()["detail"]))
        self.assertGreater(len(found), 0, "no comments in %d s: %s" % (SECONDS, adapter.view()))
        times = [c["time"] for c in found]
        self.assertEqual(times, sorted(times), "the merged list is in time order")
        self.assertEqual(len({c["id"] for c in found}), len(found), "each comment once")


if __name__ == "__main__":
    unittest.main()
