"""Twitch chat, read anonymously over IRC on TLS. No account, no key.

Twitch lets anyone read a public chat as `justinfan<digits>`. A read only
connection may join 20 channels every 10 seconds; this joins at most 20 in
all, once per connection. The server pings every five minutes or so and a
connection silent for longer than that is treated as dead.
"""
import random
import socket
import ssl

from .base import Adapter, Problem, CONNECTED
from . import twitch_parse as parse

HOST = "irc.chat.twitch.tv"
PORT = 6697
READ_TIMEOUT_S = 360


class Twitch(Adapter):
    platform = "twitch"
    title = "Twitch"

    def __init__(self, settings, sink):
        super().__init__(settings, sink)
        self.sock = None

    @classmethod
    def configured(cls, s):
        return bool(parse.channels_of(s.get("twitch_channels", "")))

    def session(self):
        channels = parse.channels_of(self.settings.get("twitch_channels", ""))
        if not channels:
            raise Problem("no Twitch channel is set",
                          "Type the channel names in Settings.", retry_s=None)
        context = ssl.create_default_context()
        raw = socket.create_connection((HOST, PORT), timeout=20)
        self.sock = context.wrap_socket(raw, server_hostname=HOST)
        self.sock.settimeout(READ_TIMEOUT_S)
        nick = "justinfan%d" % random.randint(10000, 99999)
        self.send("CAP REQ :twitch.tv/tags twitch.tv/commands")
        self.send("PASS SCHMOOPIIE")
        self.send("NICK " + nick)
        self.send("JOIN " + ",".join("#" + c for c in channels))
        self.say(CONNECTED, "reading #%s" % ", #".join(channels))
        self.read_lines()

    def read_lines(self):
        pending = b""
        while not self.stopping.is_set():
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                raise Problem("Twitch went quiet for six minutes",
                              "Reconnecting by itself.", retry_s=2) from None
            if not chunk:
                raise Problem("Twitch closed the connection", "Reconnecting by itself.",
                              retry_s=2)
            pending += chunk
            *lines, pending = pending.split(b"\r\n")
            for line in lines:
                self.handle(line.decode("utf-8", "replace"))

    def handle(self, line):
        what, value = parse.read(line)
        if what == "comment":
            self.emit(value)
        elif what == "delete":
            self.sink.remove(value)
        elif what == "clear_user":
            self.sink.remove_where(lambda c: c["platform"] == "twitch"
                                   and c.get("author_id") == value)
        elif what == "ping":
            self.send("PONG :" + value)
        elif what == "reconnect":
            raise Problem("Twitch asked for a reconnect", "Reconnecting by itself.",
                          retry_s=1)
        elif what == "notice" and "suspended" in value.lower():
            self.say(CONNECTED, "Twitch says: %s" % value[:200])

    def send(self, line):
        self.sock.sendall((line + "\r\n").encode("utf-8"))

    def close(self):
        sock, self.sock = self.sock, None
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
