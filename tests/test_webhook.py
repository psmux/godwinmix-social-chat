"""The webhook: what it reads, and a real POST to a real listener on this machine."""
import json
import socket
import time
import unittest
import urllib.error
import urllib.request

from helpers import fixture
from social_chat.adapters import webhook_parse as parse
from social_chat.adapters.webhook import Webhook
from social_chat.hub import Hub


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Reading(unittest.TestCase):
    def test_a_batch_with_every_spelling(self):
        found, skipped = parse.items(fixture("webhook_batch.json"))
        self.assertEqual(skipped, 2)
        tiktok, kick, insta = found
        self.assertEqual((tiktok["platform"], tiktok["id"], tiktok["author"]), ("tiktok", "tiktok:7301", "Sam"))
        self.assertEqual(tiktok["avatar"], "https://p16-sign.example/sam.jpg")
        self.assertEqual((kick["platform"], kick["author"], kick["text"]), ("kick", "streamfan", "first!"))
        self.assertEqual(kick["time"], 1791914400000.0)
        self.assertTrue(insta["question"])
        self.assertTrue(insta["id"].startswith("instagram:h"))

    def test_the_same_post_twice_has_the_same_id(self):
        body = {"platform": "kick", "author": "a", "text": "same words", "time": 1791914400}
        self.assertEqual(parse.one(body)["id"], parse.one(dict(body))["id"])

    def test_one_object_and_a_bare_list_are_read_too(self):
        self.assertEqual(len(parse.items({"author": "a", "text": "b"})[0]), 1)
        self.assertEqual(len(parse.items([{"author": "a", "text": "b"}, {"text": "c"}])[0]), 2)
        self.assertEqual(parse.items("nonsense"), ([], 1))

    def test_a_picture_that_is_not_a_web_address_is_dropped(self):
        self.assertNotIn("avatar", parse.one({"text": "x", "avatar": "javascript:alert(1)"}))


class Listening(unittest.TestCase):
    """Start the listener for real and post to it over HTTP."""

    def setUp(self):
        self.port = free_port()
        self.hub = Hub()
        self.adapter = Webhook({"webhook_enabled": True, "webhook_port": self.port,
                                "webhook_secret": "s3cret-for-tests"}, self.hub)
        self.adapter.start()
        for _ in range(100):
            if self.adapter.view()["state"] == "connected":
                break
            time.sleep(0.05)

    def tearDown(self):
        self.adapter.stop()

    def post(self, body, secret="s3cret-for-tests"):
        request = urllib.request.Request(
            "http://127.0.0.1:%d/comments" % self.port, data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "X-Social-Chat-Secret": secret})
        try:
            with urllib.request.urlopen(request, timeout=5) as answer:
                return answer.status, json.loads(answer.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
        except ConnectionResetError:
            # Some desktop traffic filters (AdGuard is one) reset loopback
            # connections after the answer is written. The post itself was
            # handled; the tests below then judge by the list instead.
            return None, None

    def test_posted_comments_reach_the_merged_list_once(self):
        self.assertEqual(self.adapter.view()["state"], "connected")
        status, body = self.post(fixture("webhook_batch.json"))
        if status is not None:
            self.assertEqual(status, 202)
            self.assertEqual(body, {"accepted": 3, "duplicates": 0, "skipped": 2})
        self.assertEqual(len(self.hub.snapshot()), 3)
        self.assertEqual({c["via"] for c in self.hub.snapshot()}, {"webhook"},
                         "the panel's webhook chip mutes TikTok and Kick posted here")
        status, body = self.post(fixture("webhook_batch.json"))
        if status is not None:
            self.assertEqual(body["duplicates"], 3)
        self.assertEqual(len(self.hub.snapshot()), 3)

    def test_a_wrong_secret_is_refused(self):
        status, body = self.post({"author": "x", "text": "y"}, secret="wrong")
        if status is not None:
            self.assertEqual(status, 401)
            self.assertIn("secret", body["error"])
        self.assertEqual(self.hub.snapshot(), [])
        self.post({"author": "x", "text": "y"})
        self.assertEqual(len(self.hub.snapshot()), 1, "the right secret is let in")

    def test_a_port_in_use_says_so(self):
        other = Webhook({"webhook_enabled": True, "webhook_port": self.port}, Hub())
        other.start()
        time.sleep(0.5)
        view = other.view()
        other.stop()
        self.assertEqual(view["state"], "failing")
        self.assertIn("webhook_port", view["next"])


if __name__ == "__main__":
    unittest.main()
