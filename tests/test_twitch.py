"""Twitch: reading IRC lines as Twitch documents them, with no network."""
import unittest

from helpers import fixture, Sink
from social_chat.adapters import twitch_parse as parse
from social_chat.adapters.twitch import Twitch
from social_chat.adapters.base import Problem


def lines():
    return fixture("twitch_lines.txt").decode("utf-8").split("\r\n")[:-1]


class Lines(unittest.TestCase):
    def setUp(self):
        self.read = [parse.read(line) for line in lines()]

    def test_a_chat_line_becomes_a_comment(self):
        what, c = self.read[1]
        self.assertEqual(what, "comment")
        self.assertEqual(c["id"], "twitch:5a2c4f1e-0d4b-4c8a-9d1e-7f3a2b1c0d9e")
        self.assertEqual(c["author"], "pixel_otter")
        self.assertEqual(c["text"], "what camera are you using for the wide shot?")
        self.assertEqual(c["channel"], "ourchannel")
        self.assertEqual(c["colour"], "#1E90FF")
        self.assertEqual(c["badges"], ["member"])
        self.assertEqual(c["time"], 1791914401123)
        self.assertTrue(c["question"])

    def test_an_action_loses_its_markers_and_a_broadcaster_is_the_owner(self):
        _, c = self.read[2]
        self.assertEqual(c["text"], "waves at everyone")
        self.assertEqual(c["badges"], ["owner"])
        self.assertEqual(c["author"], "OurChannel")

    def test_bits_and_subscriptions(self):
        _, cheer = self.read[3]
        self.assertEqual(cheer["kind"], "superchat")
        self.assertEqual(cheer["amount"], "100 bits")
        _, sub = self.read[4]
        self.assertEqual(sub["kind"], "member")
        self.assertTrue(sub["text"].startswith("Lofi_Gardener subscribed at Tier 1."))
        self.assertTrue(sub["text"].endswith("six months already"))

    def test_moderation_lines(self):
        self.assertEqual(self.read[5], ("delete", "twitch:5a2c4f1e-0d4b-4c8a-9d1e-7f3a2b1c0d9e"))
        self.assertEqual(self.read[6], ("clear_user", "50505050"))
        self.assertEqual(self.read[7], ("clear_all", "ourchannel"))
        self.assertEqual(self.read[8], ("ping", "tmi.twitch.tv"))
        self.assertEqual(self.read[9], ("reconnect", ""))
        self.assertEqual(self.read[0], (None, None))

    def test_tag_escapes(self):
        backslash = chr(92)
        escaped = "a{0}sb{0}:c{0}{0}d{0}r{0}n".format(backslash)
        self.assertEqual(parse.unescape(escaped), "a b;c" + backslash + "d\r\n")

    def test_channel_names_from_whatever_was_typed(self):
        self.assertEqual(parse.channels_of("#OurChannel, friends  https://www.twitch.tv/third/ x"),
                         ["ourchannel", "friends", "third"])
        self.assertEqual(parse.channels_of(""), [])


class Handling(unittest.TestCase):
    def test_the_adapter_acts_on_each_line(self):
        sink = Sink()
        adapter = Twitch({"twitch_channels": "ourchannel"}, sink)
        sent = []
        adapter.send = sent.append
        for line in lines()[:9]:
            adapter.handle(line)
        self.assertEqual(len(sink.added), 4)
        self.assertEqual(sink.removed, ["twitch:5a2c4f1e-0d4b-4c8a-9d1e-7f3a2b1c0d9e"])
        self.assertEqual(len(sink.wheres), 1)
        self.assertTrue(sink.wheres[0]({"platform": "twitch", "author_id": "50505050"}))
        self.assertFalse(sink.wheres[0]({"platform": "youtube", "author_id": "50505050"}))
        self.assertEqual(sent, ["PONG :tmi.twitch.tv"])
        with self.assertRaises(Problem):
            adapter.handle(lines()[9])


if __name__ == "__main__":
    unittest.main()
