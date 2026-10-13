"""The generic webhook: a small HTTP listener any platform or relay can POST to.

It listens on 127.0.0.1 unless the operator says otherwise, because a port
that puts words on a programme should not be open to the network by default.
With `webhook_secret` set, a request must carry it in `X-Social-Chat-Secret`
or as `Authorization: Bearer <secret>`.
"""
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .base import Adapter, Problem, CONNECTED
from . import webhook_parse as parse

MAX_BODY = 256 * 1024


class Webhook(Adapter):
    platform = "webhook"
    title = "Webhook"

    def __init__(self, settings, sink):
        super().__init__(settings, sink)
        self.server = None

    @classmethod
    def configured(cls, s):
        return bool(s.get("webhook_enabled"))

    def session(self):
        bind = self.settings.get("webhook_bind") or "127.0.0.1"
        port = int(self.settings.get("webhook_port") or 8790)
        try:
            self.server = ThreadingHTTPServer((bind, port), self.handler())
        except OSError as e:
            raise Problem("could not listen on %s:%d (%s)" % (bind, port, e.strerror or e),
                          "Pick another webhook_port in Settings, or stop what is "
                          "using that one.", retry_s=60) from None
        self.server.daemon_threads = True
        self.say(CONNECTED, "listening on http://%s:%d/comments" % (bind, port))
        self.server.serve_forever(poll_interval=0.5)

    def close(self):
        server, self.server = self.server, None
        if server is not None:
            server.shutdown()
            server.server_close()

    def accept(self, payload):
        found, skipped = parse.items(payload)
        before = self.count
        for item in found:
            self.emit(item)
        added = self.count - before
        return {"accepted": added, "duplicates": len(found) - added, "skipped": skipped}

    def allowed(self, headers):
        secret = self.settings.get("webhook_secret") or ""
        if not secret:
            return True
        given = headers.get("X-Social-Chat-Secret") or ""
        auth = headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            given = given or auth[7:].strip()
        return hmac.compare_digest(given.encode(), secret.encode())

    def handler(self):
        adapter = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "social-chat"

            def do_GET(self):
                self.answer(200, {"ok": True, "post": "/comments",
                                  "accepted_so_far": adapter.count})

            def do_POST(self):
                if self.path.split("?")[0] not in ("/", "/comments"):
                    return self.answer(404, {"error": "POST to /comments"})
                if not adapter.allowed(self.headers):
                    return self.answer(401, {"error": "the webhook secret is missing or "
                                             "wrong; send it in X-Social-Chat-Secret"})
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0 or length > MAX_BODY:
                    return self.answer(413, {"error": "send a JSON body of at most 256 KB"})
                try:
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                except ValueError:
                    return self.answer(400, {"error": "the body is not JSON"})
                self.answer(202, adapter.accept(payload))

            def answer(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):  # stderr is the control channel
                pass

        return Handler
