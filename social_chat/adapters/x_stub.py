"""X (formerly Twitter): a stub, on purpose.

Reading replies to a live post needs the X API's filtered stream or recent
search, and neither is in the free tier: they need the paid Basic tier or
above. Rather than pretend, this adapter says so when it is switched on and
does nothing else. docs/adapters.md describes what a working one would do,
for anyone who has a paid key; the webhook adapter is the other way in, for a
relay that already reads X.
"""
from .base import Adapter, Problem, UNAVAILABLE


class X(Adapter):
    platform = "x"
    title = "X"

    @classmethod
    def configured(cls, s):
        return bool(s.get("x_enabled"))

    def session(self):
        raise Problem("reading X needs a paid X API plan, and this adapter is a stub",
                      "Send X replies in through the webhook from a tool that "
                      "already reads them, or see docs/adapters.md to write this one.",
                      retry_s=None, state=UNAVAILABLE)
