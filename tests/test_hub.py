"""The merged list: time order across platforms, once each, and what changed."""
import threading
import time
import unittest

import helpers  # noqa: F401  (puts the plugin on the path)
from social_chat.hub import Hub
from social_chat.model import comment, now_ms

BASE = 1791914400000


def c(platform, native, at, text="hi"):
    return comment(platform, native, "someone", text, BASE + at)


class Merge(unittest.TestCase):
    def test_comments_from_several_platforms_come_out_in_time_order(self):
        hub = Hub()
        hub.add(c("twitch", "t1", 300))
        hub.add(c("youtube", "y1", 100))
        hub.add(c("facebook", "f1", 200))
        hub.add(c("youtube", "y2", 400))
        hub.add(c("twitch", "t0", 50))  # late: an earlier comment arriving after newer ones
        self.assertEqual([x["id"] for x in hub.snapshot()],
                         ["twitch:t0", "youtube:y1", "facebook:f1", "twitch:t1", "youtube:y2"])

    def test_the_same_moment_keeps_the_order_of_arrival(self):
        hub = Hub()
        for n in range(5):
            hub.add(c("webhook", "w%d" % n, 0))
        self.assertEqual([x["id"] for x in hub.snapshot()], ["webhook:w%d" % n for n in range(5)])

    def test_a_platform_clock_running_ahead_is_pulled_back(self):
        hub = Hub()
        hub.add(comment("x", "future", "a", "b", now_ms() + 60_000))
        hub.add(comment("x", "now", "a", "b", now_ms() - 1000))
        self.assertEqual([x["id"] for x in hub.snapshot()], ["x:now", "x:future"])
        self.assertLess(hub.get("x:future")["time"], now_ms() + 1000)


class Dedupe(unittest.TestCase):
    def test_a_comment_is_added_once_even_after_it_scrolled_off(self):
        hub = Hub(keep=50)
        self.assertTrue(hub.add(c("youtube", "a", 1)))
        self.assertFalse(hub.add(c("youtube", "a", 1)))
        for n in range(60):
            hub.add(c("twitch", str(n), 10 + n))
        self.assertIsNone(hub.get("youtube:a"))
        self.assertFalse(hub.add(c("youtube", "a", 1)), "a backlog read again after a reconnect")
        self.assertEqual(len(hub.snapshot()), 50)

    def test_the_same_native_id_on_two_platforms_is_two_comments(self):
        hub = Hub()
        self.assertTrue(hub.add(c("youtube", "1", 1)))
        self.assertTrue(hub.add(c("twitch", "1", 1)))


class Changes(unittest.TestCase):
    def test_a_reader_gets_only_what_changed_since_its_number(self):
        hub = Hub()
        hub.add(c("youtube", "a", 1))
        first = hub.changes_since(0)
        self.assertTrue(first["reset"])
        hub.add(c("youtube", "b", 2))
        hub.remove("youtube:a")
        later = hub.changes_since(first["seq"])
        self.assertFalse(later["reset"])
        self.assertEqual([x["id"] for x in later["added"]], ["youtube:b"])
        self.assertEqual(later["removed"], ["youtube:a"])
        self.assertEqual(hub.changes_since(later["seq"])["added"], [])

    def test_a_reader_from_another_process_starts_again(self):
        hub = Hub()
        hub.add(c("youtube", "a", 1))
        self.assertTrue(hub.changes_since(999)["reset"])

    def test_remove_where_takes_away_one_authors_comments(self):
        hub = Hub()
        hub.add(comment("twitch", "1", "spam", "buy now", BASE, author_id="9"))
        hub.add(comment("twitch", "2", "fine", "hello", BASE, author_id="8"))
        self.assertEqual(hub.remove_where(lambda x: x.get("author_id") == "9"), 1)
        self.assertEqual([x["id"] for x in hub.snapshot()], ["twitch:2"])

    def test_a_long_poll_wakes_when_a_comment_arrives(self):
        hub = Hub()
        threading.Timer(0.2, lambda: hub.add(c("twitch", "late", 1))).start()
        started = time.monotonic()
        hub.wait(0, 3.0)
        self.assertLess(time.monotonic() - started, 2.0)
        started = time.monotonic()
        hub.wait(hub.seq, 0.3)
        self.assertGreaterEqual(time.monotonic() - started, 0.25)


if __name__ == "__main__":
    unittest.main()
