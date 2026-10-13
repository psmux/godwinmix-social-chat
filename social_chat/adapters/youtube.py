"""YouTube live chat, polled with the YouTube Data API v3.

Quota is what limits this adapter. A project gets 10,000 units a day by
default; reading the chat costs 5 units a call, finding a video's chat costs
1, and finding a channel's live video costs 100 (search.list). So the chat id
is looked up once per connection, and the chat is polled no faster than the
`pollingIntervalMillis` YouTube returns with every answer, nor faster than
the operator's own floor, `youtube_min_poll_seconds`.
"""
import json
import urllib.parse
import urllib.request

from .. import redact, web
from .base import Adapter, Problem, CONNECTED, WAITING, UNAVAILABLE
from . import youtube_parse as parse

API = "https://www.googleapis.com/youtube/v3/"
TOKEN_URL = "https://oauth2.googleapis.com/token"


class YouTube(Adapter):
    platform = "youtube"
    title = "YouTube"

    @classmethod
    def configured(cls, s):
        return bool(s.get("youtube_api_key") or s.get("youtube_oauth_token")
                    or s.get("youtube_refresh_token"))

    def session(self):
        chat, title = self.find_chat()
        self.say(CONNECTED, "reading the live chat of %s" % (title or "the stream"))
        page = None
        while not self.stopping.is_set():
            query = {"liveChatId": chat, "part": "id,snippet,authorDetails",
                     "maxResults": 500}
            if page:
                query["pageToken"] = page
            read = parse.messages(self.call("liveChat/messages", query), "youtube")
            for item in read["comments"]:
                self.emit(item)
            for gone in read["deleted"]:
                self.sink.remove(gone)
            for author in read["banned"]:
                self.sink.remove_where(lambda c, a=author: c.get("author_id") == a
                                       and c["platform"] == "youtube")
            if read["ended"]:
                raise Problem("the live chat has ended", "Start a new stream, then "
                              "press Reconnect or paste its address.", retry_s=60,
                              state=WAITING)
            page = read["next_page"] or page
            floor = float(self.settings.get("youtube_min_poll_seconds") or 0)
            if self.wait(max(read["interval_ms"] / 1000.0, floor, 1.0)):
                return

    # Finding the chat.

    def find_chat(self):
        kind, value = parse.target_of(self.settings.get("youtube_video", ""))
        if kind == "unknown":
            raise Problem("'%s' is not a YouTube video, channel or handle" % value,
                          "Paste the stream's address, such as "
                          "https://www.youtube.com/watch?v=..., or the channel's @handle.",
                          retry_s=None)
        if kind == "mine":
            if not self.oauth():
                raise Problem("no video or channel is set, and finding your own "
                              "stream needs OAuth", "Paste the stream's address in "
                              "Settings, or add an OAuth token.", retry_s=None)
            chat, title = parse.chat_id_of_broadcasts(self.call(
                "liveBroadcasts", {"part": "snippet", "broadcastStatus": "active",
                                   "broadcastType": "all"}))
            return self._live_or_wait(chat, title, "your channel")
        if kind == "handle":
            value = parse.first_id(self.call("channels", {"part": "id",
                                                          "forHandle": value}))
            if not value:
                raise Problem("no YouTube channel has that handle",
                              "Check the @handle in Settings.", retry_s=None)
            kind = "channel"
        if kind == "channel":
            value = parse.first_id(self.call("search", {
                "part": "id", "channelId": value, "eventType": "live",
                "type": "video", "maxResults": 1}))
            if not value:
                return self._live_or_wait(None, "", "the channel")
        chat, title = parse.chat_id_of_video(self.call(
            "videos", {"part": "liveStreamingDetails,snippet", "id": value}))
        return self._live_or_wait(chat, title, "that video")

    def _live_or_wait(self, chat, title, what):
        if chat:
            return chat, title
        raise Problem("%s is not live, or its chat is off" % what,
                      "Go live, then wait: this checks again every two minutes. "
                      "Pasting the stream's own address costs less quota than a channel.",
                      retry_s=120, state=WAITING)

    # Calling the API.

    def oauth(self):
        return bool(self.settings.get("youtube_oauth_token")
                    or self.settings.get("youtube_refresh_token"))

    def call(self, path, query, retried=False):
        headers = {}
        if self.oauth():
            if not self.settings.get("youtube_oauth_token"):
                self.refresh()
            headers["Authorization"] = "Bearer " + self.settings["youtube_oauth_token"]
        else:
            query = dict(query, key=self.settings.get("youtube_api_key", ""))
        url = API + path + "?" + urllib.parse.urlencode(query)
        try:
            return web.get_json(url, headers)
        except web.HttpError as e:
            if e.status == 401 and self.settings.get("youtube_refresh_token") and not retried:
                self.refresh()
                return self.call(path, query, retried=True)
            raise problem_of(e) from None

    def refresh(self):
        s = self.settings
        if not (s.get("youtube_client_id") and s.get("youtube_client_secret")
                and s.get("youtube_refresh_token")):
            raise Problem("the OAuth token has expired and cannot be renewed here",
                          "Add the client id, client secret and refresh token in "
                          "Settings, or paste a fresh access token.", retry_s=None)
        body = urllib.parse.urlencode({
            "client_id": s["youtube_client_id"], "client_secret": s["youtube_client_secret"],
            "refresh_token": s["youtube_refresh_token"], "grant_type": "refresh_token"})
        request = urllib.request.Request(TOKEN_URL, data=body.encode(), method="POST")
        try:
            with urllib.request.urlopen(request, timeout=15) as answer:
                token = json.loads(answer.read().decode()).get("access_token")
        except Exception:
            token = None
        if not token:
            raise Problem("Google would not renew the OAuth token",
                          "Make a new refresh token and paste it in Settings.",
                          retry_s=None)
        redact.register(token)
        s["youtube_oauth_token"] = token


def problem_of(error):
    """Turn a Data API refusal into what the operator reads and does next."""
    reason, message = parse.error_reason(error.body)
    if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
        return Problem("YouTube's daily quota for this API key is used up",
                       "It resets at midnight Pacific time. Raise "
                       "youtube_min_poll_seconds to spend less, or ask Google for more "
                       "quota in the Cloud console.", retry_s=1800)
    if reason in ("keyInvalid", "keyExpired") or "API key" in message:
        return Problem("YouTube refused the API key",
                       "Check the key in Settings, and that the YouTube Data API v3 "
                       "is enabled for its project.", retry_s=None)
    if reason == "accessNotConfigured" or "has not been used" in message:
        return Problem("the YouTube Data API v3 is not enabled for this key's project",
                       "Enable it in the Google Cloud console, then press Reconnect.",
                       retry_s=None, state=UNAVAILABLE)
    if error.status == 401:
        return Problem("YouTube refused the OAuth token",
                       "Paste a fresh token, or add a refresh token.", retry_s=None)
    if reason in ("liveChatEnded", "liveChatNotFound", "liveChatDisabled"):
        return Problem("the live chat is not there any more (%s)" % reason,
                       "Start a new stream, then press Reconnect.", retry_s=120,
                       state=WAITING)
    if reason == "forbidden" or error.status == 403:
        return Problem("YouTube would not show this chat: %s" % (message or reason),
                       "The chat may be members only or private.", retry_s=300)
    return Problem("YouTube answered %d %s" % (error.status, reason or message),
                   "It will try again by itself.", retry_s=30)
