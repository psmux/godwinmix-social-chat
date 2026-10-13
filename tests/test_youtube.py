"""YouTube: reading the documented liveChatMessages and videos answers."""
import unittest

from helpers import fixture, Sink
from social_chat.adapters import youtube_parse as parse
from social_chat.adapters.youtube import YouTube, problem_of
from social_chat.adapters.base import Problem, WAITING
from social_chat.web import HttpError


class Targets(unittest.TestCase):
    def test_every_way_of_naming_a_stream(self):
        cases = {
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10": ("video", "dQw4w9WgXcQ"),
            "https://youtu.be/dQw4w9WgXcQ": ("video", "dQw4w9WgXcQ"),
            "https://www.youtube.com/live/dQw4w9WgXcQ?si=abc": ("video", "dQw4w9WgXcQ"),
            "dQw4w9WgXcQ": ("video", "dQw4w9WgXcQ"),
            "https://www.youtube.com/channel/UCsampleChannelGGGGGGGGG": ("channel", "UCsampleChannelGGGGGGGGG"),
            "https://www.youtube.com/@ourchannel": ("handle", "@ourchannel"),
            "@ourchannel": ("handle", "@ourchannel"),
            "": ("mine", ""),
            "not a youtube thing at all!": ("unknown", "not a youtube thing at all!"),
        }
        for text, expected in cases.items():
            self.assertEqual(parse.target_of(text), expected, text)

    def test_the_chat_id_comes_off_the_video(self):
        chat, title = parse.chat_id_of_video(fixture("youtube_videos.json"))
        self.assertEqual(chat, "Cg0KC2RRdzR3OVdnWGNR")
        self.assertEqual(title, "Sunday service, live")
        self.assertEqual(parse.chat_id_of_video({"items": []}), (None, ""))


class Messages(unittest.TestCase):
    def setUp(self):
        self.read = parse.messages(fixture("youtube_messages.json"), "youtube")
        self.by_id = {c["id"]: c for c in self.read["comments"]}

    def test_text_super_chat_sticker_and_member_are_comments(self):
        self.assertEqual(sorted(self.by_id), ["youtube:LCC.sample-member-4", "youtube:LCC.sample-sticker-3",
                                              "youtube:LCC.sample-super-2", "youtube:LCC.sample-text-1"])
        text = self.by_id["youtube:LCC.sample-text-1"]
        self.assertEqual(text["author"], "Priya N.")
        self.assertEqual(text["text"], "Hello from Leeds!")
        self.assertEqual(text["badges"], ["member"])
        self.assertTrue(text["avatar"].startswith("https://yt4.ggpht.com/"))
        self.assertAlmostEqual(text["time"], 1791914401123.456, places=0)

    def test_a_super_chat_carries_its_amount_and_its_words(self):
        paid = self.by_id["youtube:LCC.sample-super-2"]
        self.assertEqual(paid["kind"], "superchat")
        self.assertEqual(paid["amount"], "$5.00")
        self.assertEqual(paid["text"], "Can you explain step two again?")
        self.assertTrue(paid["question"])
        self.assertEqual(self.by_id["youtube:LCC.sample-sticker-3"]["text"], "A dancing cat")

    def test_deletions_bans_and_the_next_poll_are_read(self):
        self.assertEqual(self.read["deleted"], ["youtube:LCC.sample-old-0"])
        self.assertEqual(self.read["banned"], ["UCsampleSpamFFFFFFFFFFFFF"])
        self.assertEqual(self.read["next_page"], "GO-sample-next-page")
        self.assertEqual(self.read["interval_ms"], 6012)
        self.assertFalse(self.read["ended"])

    def test_an_ended_chat_says_so(self):
        self.assertTrue(parse.messages(fixture("youtube_ended.json"))["ended"])


class Polling(unittest.TestCase):
    """The adapter waits as long as YouTube asks, and never less than the floor."""

    def run_session(self, floor):
        pages = [fixture("youtube_videos.json"), fixture("youtube_messages.json"),
                 fixture("youtube_ended.json")]
        adapter = YouTube({"youtube_api_key": "AIzaSyTestTestTestTest", "youtube_video": "dQw4w9WgXcQ",
                           "youtube_min_poll_seconds": floor}, Sink())
        calls, waits = [], []
        adapter.call = lambda path, query, retried=False: (calls.append((path, query)), pages.pop(0))[1]
        adapter.wait = lambda seconds: waits.append(seconds) and False
        with self.assertRaises(Problem) as ended:
            adapter.session()
        return adapter, calls, waits, ended.exception

    def test_the_interval_youtube_returns_is_honoured(self):
        adapter, calls, waits, ended = self.run_session(floor=1)
        self.assertEqual([c[0] for c in calls], ["videos", "liveChat/messages", "liveChat/messages"])
        self.assertAlmostEqual(waits[0], 6.012)
        self.assertEqual(calls[2][1]["pageToken"], "GO-sample-next-page")
        self.assertEqual(ended.state, WAITING)
        self.assertEqual(len(adapter.sink.added), 4)
        self.assertEqual(adapter.sink.removed, ["youtube:LCC.sample-old-0"])

    def test_the_operators_floor_wins_when_it_is_slower(self):
        _, _, waits, _ = self.run_session(floor=20)
        self.assertEqual(waits[0], 20)


class Refusals(unittest.TestCase):
    def test_quota_says_when_it_resets_and_retries_late(self):
        p = problem_of(HttpError(403, fixture("youtube_quota.json")))
        self.assertIn("quota", p.detail)
        self.assertIn("midnight Pacific", p.next_step)
        self.assertGreaterEqual(p.retry_s, 1800)

    def test_a_bad_key_stops_trying_and_says_where_to_fix_it(self):
        p = problem_of(HttpError(400, fixture("youtube_badkey.json")))
        self.assertIn("API key", p.detail)
        self.assertIsNone(p.retry_s)


if __name__ == "__main__":
    unittest.main()
