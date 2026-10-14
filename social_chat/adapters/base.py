"""What every platform adapter is, and the loop that keeps one connected.

An adapter is a class with a `platform` name, a `title`, a `configured`
check on the settings and a `session` method that connects, reads until
something goes wrong, and returns or raises. The base class runs `session` on
its own thread, again and again, with a growing wait after each failure, and
keeps the connection state in words an operator can act on.

docs/adapters.md walks through writing a new one.
"""
import threading
import time

from ..model import now_ms

BACKOFF_FIRST_S = 2.0
BACKOFF_MAX_S = 120.0

# The states a platform can be in, as the panel shows them.
OFF = "off"                  # not set up, or switched off
CONNECTING = "connecting"
CONNECTED = "connected"      # reading comments
WAITING = "waiting"          # set up, nothing to read yet (no live stream)
FAILING = "failing"          # tried and failed; `next` says what to do
UNAVAILABLE = "unavailable"  # this platform cannot work here at all


class Problem(Exception):
    """A failure with the words to show for it.

    `retry_s` is how long to wait before trying again, or None to stop
    trying until the settings change (a wrong key will not fix itself).
    """

    def __init__(self, detail, next_step, retry_s=30.0, state=FAILING):
        super().__init__(detail)
        self.detail = detail
        self.next_step = next_step
        self.retry_s = retry_s
        self.state = state


class Adapter:
    platform = "base"
    title = "Base"

    def __init__(self, settings, sink):
        """`sink` has add(comment), remove(id) and remove_where(test)."""
        self.settings = settings
        self.sink = sink
        self.stopping = threading.Event()
        self.thread = None
        self.count = 0
        self.status = {"platform": self.platform, "title": self.title,
                       "state": OFF, "detail": "", "next": "", "since": now_ms(),
                       "count": 0}

    @classmethod
    def configured(cls, settings):
        return False

    # What a subclass writes.

    def session(self):
        """Connect and read until stopped. Return or raise to be run again."""
        raise NotImplementedError

    # What a subclass calls.

    def emit(self, item):
        item.setdefault("via", self.platform)  # which adapter, for the panel's chips
        if self.sink.add(item):
            self.count += 1
            self.status["count"] = self.count

    def say(self, state, detail, next_step=""):
        if (state, detail, next_step) != (self.status["state"], self.status["detail"],
                                          self.status["next"]):
            self.status.update(state=state, detail=detail, next=next_step,
                               since=now_ms())

    def wait(self, seconds):
        """Sleep, but wake at once when asked to stop. True means stop."""
        return self.stopping.wait(max(0.0, seconds))

    # The loop.

    def start(self):
        self.thread = threading.Thread(target=self._loop, name=self.platform,
                                       daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()
        self.close()

    def close(self):
        """Drop whatever connection is open. A blocking read returns."""

    def view(self):
        return dict(self.status)

    def _loop(self):
        delay = BACKOFF_FIRST_S
        while not self.stopping.is_set():
            self.say(CONNECTING, "connecting to %s" % self.title)
            started = time.monotonic()
            try:
                self.session()
                retry = 1.0
            except Problem as problem:
                self.say(problem.state, problem.detail, problem.next_step)
                if problem.retry_s is None:
                    return
                retry = problem.retry_s
            except Exception as e:  # a bug or a network error we did not name
                self.say(FAILING, "%s stopped: %s" % (self.title, describe(e)),
                         "It will try again by itself. If this keeps happening, "
                         "check this machine's internet connection.")
                retry = delay
            finally:
                self.close()
            if time.monotonic() - started > 60:
                delay = BACKOFF_FIRST_S
            else:
                delay = min(BACKOFF_MAX_S, delay * 2)
            if self.wait(max(retry, 1.0)):
                return


def describe(error):
    text = str(error) or error.__class__.__name__
    return text[:300]
