"""Practice mode: made up comments from made up people, for a rehearsal.

Switched on with `practice_mode`, it sends a comment every few seconds as if
from YouTube, Twitch and Facebook, so an operator can try the panel and the
on air card before a real chat is connected. Every name here is invented.
"""
import itertools
import random

from ..model import comment, now_ms
from .base import Adapter, CONNECTED

SAMPLES = [
    ("youtube", "Priya N.", "Greetings from Leeds! The sound is so much better this week"),
    ("twitch", "pixel_otter", "what camera are you using for the wide shot?"),
    ("facebook", "Marta Lindqvist", "Watching with the whole family tonight"),
    ("youtube", "Dev Okafor", "Can you explain the second step again? I missed it"),
    ("twitch", "QuietKestrel", "first time catching this live, hello everyone"),
    ("facebook", "Tom Reyes", "Is there a recording for people who join late?"),
    ("youtube", "Hana Sato", "That transition was smooth"),
    ("twitch", "lofi_gardener", "chat is moving fast today"),
    ("facebook", "Grace Mbeki", "Shared this with our choir group"),
    ("youtube", "Luis Ortega", "How long have you been streaming with this setup?"),
    ("twitch", "neon_tortoise", "the lower thirds look great"),
    ("facebook", "Ines Duarte", "Hello from Porto!"),
    ("youtube", "Amara Diallo", "Could you put the recipe link in the description?"),
    ("twitch", "copper_heron", "LOL the cat walking across the desk"),
    ("facebook", "Wen Li", "Our whole office is watching on the big screen today"),
    ("youtube", "Jonas Berg", "What microphone is that? It sounds really warm"),
    ("twitch", "midnight_ferret", "hi from Brazil"),
    ("facebook", "Fatima Rahman", "Thank you for doing this every week, it helps a lot"),
    ("youtube", "Theo Martin", "Is the Q&A at the end or now?"),
    ("twitch", "saltwater_lynx", "the new overlay is clean"),
]


class Practice(Adapter):
    platform = "practice"
    title = "Practice"

    @classmethod
    def configured(cls, s):
        return bool(s.get("practice_mode"))

    def session(self):
        self.say(CONNECTED, "sending made up comments for a rehearsal")
        for n in itertools.count():
            platform, author, text = SAMPLES[n % len(SAMPLES)]
            item = comment(platform, "practice-%d-%d" % (int(now_ms()), n), author, text,
                           author_id="practice-" + author.lower().replace(" ", "-"))
            item["practice"] = True
            self.emit(item)
            if self.wait(random.uniform(2.0, 5.0)):
                return
