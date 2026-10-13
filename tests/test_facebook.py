"""Facebook: the comments edge, the live_comments stream and the refusals."""
import io
import unittest

from helpers import fixture, Sink
from social_chat import web
from social_chat.adapters import facebook_parse as parse
from social_chat.adapters.facebook import Facebook, problem_of
from social_chat.adapters.base import Problem


class Reading(unittest.TestCase):
    def test_a_page_of_comments_oldest_first_without_the_empty_one(self):
        found = parse.page(fixture("facebook_comments.json"), "1234567890123456")
        self.assertEqual([c["text"] for c in found],
                         ["Hello from Porto!", "Is there a recording for people who join late?"])
        porto, tom = found
        self.assertEqual(porto["author"], "Facebook user")
        self.assertEqual(tom["author"], "Tom Reyes")
        self.assertEqual(tom["avatar"], "https://scontent.xx.fbcdn.net/sample-tom.jpg")
        self.assertEqual(tom["id"], "facebook:1234567890123456_9000000000000003")
        self.assertTrue(tom["question"])
        self.assertEqual(tom["time"], 1791914409000.0)

    def test_the_event_stream_including_a_bad_event_and_a_split_one(self):
        stream = io.BytesIO(fixture("facebook_live_comments.sse"))
        datas = list(web.events(stream))
        self.assertEqual(len(datas), 3)
        found = [parse.event(d) for d in datas]
        self.assertIsNone(found[1])
        self.assertEqual(found[0]["author"], "Marta Lindqvist")
        self.assertEqual(found[2]["text"], "Shared this with our choir")

    def test_the_live_video_of_the_page(self):
        self.assertEqual(parse.live_video(fixture("facebook_live_videos.json")),
                         ("1234567890123456", "Choir rehearsal"))
        self.assertEqual(parse.live_video({"data": []}), (None, ""))

    def test_a_video_from_what_was_pasted(self):
        self.assertEqual(parse.video_of("https://www.facebook.com/ourpage/videos/1234567890123456/"),
                         "1234567890123456")
        self.assertEqual(parse.video_of("https://www.facebook.com/watch/?v=1234567890123456"),
                         "1234567890123456")
        self.assertEqual(parse.video_of("https://www.facebook.com/ourpage/videos/choir-night/1234567890123456"),
                         "1234567890123456")
        self.assertEqual(parse.video_of("1234567890123456"), "1234567890123456")
        self.assertEqual(parse.video_of("our page"), "")


class Session(unittest.TestCase):
    def test_a_refused_stream_falls_back_to_polling(self):
        sink = Sink()
        fb = Facebook({"facebook_page_token": "EAAsampletoken", "facebook_live_video": "1234567890123456",
                       "facebook_poll_seconds": 2}, sink)

        def refuse(video, title):
            raise web.HttpError(400, {"error": {"code": 2, "message": "unsupported"}})

        fb.read_stream = refuse
        fb.get = lambda url, query: fixture("facebook_comments.json")
        fb.wait = lambda s: True  # stop after one poll
        fb.session()
        self.assertTrue(fb.polling)
        self.assertEqual(len(sink.added), 2)

    def test_an_expired_token_stops_and_says_what_to_do(self):
        p = problem_of(web.HttpError(400, fixture("facebook_expired.json")))
        self.assertIn("token", p.detail)
        self.assertIsNone(p.retry_s)
        self.assertIn("Page token", p.next_step)

    def test_a_page_that_is_not_live_waits(self):
        fb = Facebook({"facebook_page_token": "EAAsampletoken"}, Sink())
        fb.get = lambda url, query: {"data": []}
        with self.assertRaises(Problem) as waited:
            fb.find_video()
        self.assertEqual(waited.exception.state, "waiting")


if __name__ == "__main__":
    unittest.main()
