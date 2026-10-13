"""Facebook Live comments, with a Page access token the operator pastes.

The event stream (`streaming-graph.facebook.com/<id>/live_comments`) is one
long request that Facebook pushes comments down, which costs one call for
the whole stream. Where it is refused (some tokens and some video ids cannot
use it) the adapter falls back to polling the `comments` edge every
`facebook_poll_seconds`, newest first, and lets the merge drop what it has.
"""
import urllib.parse

from .. import web
from .base import Adapter, Problem, CONNECTED, WAITING
from . import facebook_parse as parse

GRAPH = "https://graph.facebook.com/v21.0/"
STREAM = "https://streaming-graph.facebook.com/"
FIELDS = "id,message,created_time,from{id,name,picture}"
RATE_LIMITED = (4, 17, 32, 613, 80001)


class Facebook(Adapter):
    platform = "facebook"
    title = "Facebook"

    def __init__(self, settings, sink):
        super().__init__(settings, sink)
        self.stream = None
        self.polling = settings.get("facebook_mode") == "poll"

    @classmethod
    def configured(cls, s):
        return bool(s.get("facebook_page_token"))

    def session(self):
        video, title = self.find_video()
        if not self.polling:
            try:
                return self.read_stream(video, title)
            except web.HttpError as e:
                code, _ = parse.error_of(e.body)
                if e.status == 401 or code == 190 or code in RATE_LIMITED:
                    raise problem_of(e) from None
                self.polling = True  # the stream is refused here; poll instead
        self.poll(video, title)

    def find_video(self):
        pasted = self.settings.get("facebook_live_video", "")
        video = parse.video_of(pasted)
        if pasted.strip() and not video:
            raise Problem("'%s' does not name a Facebook video" % pasted[:80],
                          "Paste the live video's address or its number.", retry_s=None)
        if video:
            return video, ""
        found, title = parse.live_video(self.get(GRAPH + "me/live_videos", {
            "broadcast_status": '["LIVE"]', "fields": "id,title,status"}))
        if not found:
            raise Problem("the Page is not live", "Go live on the Page; this checks "
                          "again every minute.", retry_s=60, state=WAITING)
        return found, title

    def read_stream(self, video, title):
        query = {"access_token": self.token(), "comment_rate": "ten_per_second",
                 "fields": "id,message,created_time,from{id,name}"}
        self.stream = web.open_stream(STREAM + video + "/live_comments?"
                                      + urllib.parse.urlencode(query), timeout=300)
        self.say(CONNECTED, "streaming comments on %s" % (title or "the live video"))
        for data in web.events(self.stream):
            if self.stopping.is_set():
                return
            item = parse.event(data, video)
            if item:
                self.emit(item)
        raise Problem("Facebook ended the comment stream", "Reconnecting by itself.",
                      retry_s=5)

    def poll(self, video, title):
        self.say(CONNECTED, "polling comments on %s" % (title or "the live video"))
        every = max(2.0, float(self.settings.get("facebook_poll_seconds") or 5))
        while not self.stopping.is_set():
            answer = self.get(GRAPH + video + "/comments", {
                "order": "reverse_chronological", "filter": "stream",
                "live_filter": "no_filter", "fields": FIELDS, "limit": 50})
            for item in parse.page(answer, video):
                self.emit(item)
            if self.wait(every):
                return

    def get(self, url, query):
        query = dict(query, access_token=self.token())
        try:
            return web.get_json(url + "?" + urllib.parse.urlencode(query))
        except web.HttpError as e:
            raise problem_of(e) from None

    def token(self):
        return self.settings.get("facebook_page_token", "")

    def close(self):
        stream, self.stream = self.stream, None
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass


def problem_of(error):
    code, message = parse.error_of(error.body)
    if code == 190 or error.status == 401:
        return Problem("Facebook refused the Page access token (expired or revoked)",
                       "Make a new Page token, paste it in Settings and press Save.",
                       retry_s=None)
    if code in RATE_LIMITED:
        return Problem("Facebook is rate limiting this token",
                       "It will try again in five minutes. Raise "
                       "facebook_poll_seconds if this keeps happening.", retry_s=300)
    if code in (10, 200, 283) or error.status == 403:
        return Problem("the token may not read this video's comments: %s" % message[:160],
                       "Use a Page token with pages_read_engagement and "
                       "pages_read_user_content, from the Page that is live.",
                       retry_s=None)
    if code == 100:
        return Problem("Facebook does not know that video: %s" % message[:160],
                       "Check the live video address in Settings.", retry_s=None)
    return Problem("Facebook answered %d (%s)" % (error.status, message[:160] or code),
                   "It will try again by itself.", retry_s=30)
