"""The generic webhook: a small HTTP listener any platform or relay can POST to.

It listens on 127.0.0.1 unless the operator says otherwise, because a port
that puts words on a programme should not be open to the network by default.
With `webhook_secret` set, a request must carry it in `X-Social-Chat-Secret`
or as `Authorization: Bearer <secret>`.
"""
import hmac
import json
import socket
import socketserver
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from .base import Adapter, Problem, CONNECTED
from . import webhook_parse as parse

MAX_BODY = 256 * 1024


class Server(HTTPServer):
    """One listener per port, one request at a time.

    Posts are small and a relay sends a few a second at most, so one thread is
    plenty, and each connection has ten seconds to say what it wants. (The
    threading server resets connections on some Windows machines once the
    answer is written.) Windows lets a second socket share a port that has
    SO_REUSEADDR, which would split the posts between two processes, so there
    the port is taken exclusively instead."""

    allow_reuse_address = sys.platform != "win32"

    def server_bind(self):
        if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        socketserver.TCPServer.server_bind(self)  # no reverse DNS lookup of our own name
        host, port = self.server_address[:2]
        self.server_name, self.server_port = str(host), port


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
            self.server = Server((bind, port), self.handler())
        except OSError as e:
            raise Problem("could not listen on %s:%d (%s)" % (bind, port, e.strerror or e),
                          "Pick another webhook_port in Settings, or stop what is "
                          "using that one.", retry_s=10) from None
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
            protocol_version = "HTTP/1.1"  # every answer has a length; the sender closes
            timeout = 10

            def do_GET(self):
                self.answer(200, {"ok": True, "post": "/comments",
                                  "accepted_so_far": adapter.count})

            def do_POST(self):
                # The body is read before any answer, even a refusal: a reply
                # sent over unread bytes makes Windows reset the connection,
                # and the sender then sees an error instead of the reason.
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0 or length > MAX_BODY:
                    self.close_connection = True
                    return self.answer(413, {"error": "send a JSON body of at most 256 KB"})
                raw = self.rfile.read(length)
                if self.path.split("?")[0] not in ("/", "/comments"):
                    return self.answer(404, {"error": "POST to /comments"})
                if not adapter.allowed(self.headers):
                    return self.answer(401, {"error": "the webhook secret is missing or "
                                             "wrong; send it in X-Social-Chat-Secret"})
                try:
                    payload = json.loads(raw.decode("utf-8"))
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
