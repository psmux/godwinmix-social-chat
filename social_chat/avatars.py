"""Profile pictures, fetched once and handed out as data URIs.

The mixer's page only loads pictures from its own address, so the panel
cannot show `https://yt3.ggpht.com/...` directly. This fetches each picture
once, small, and keeps a few hundred in memory. The on air card takes a
picture only when it fits in a template field (2,000 characters), which a
40 pixel JPEG from YouTube usually does.
"""
import re
import threading
from collections import OrderedDict

from . import web
from .card import data_uri

KEEP = 300
PANEL_SIZE = 64
CARD_SIZE = 40
MAX_BYTES = 60_000


def sized(url, pixels):
    """Ask YouTube's and Google's image servers for a small copy."""
    if re.search(r"=s\d+", url):
        return re.sub(r"=s\d+", "=s%d" % pixels, url, count=1)
    if "ggpht.com" in url or "googleusercontent.com" in url:
        return url + "=s%d" % pixels
    return url


class Avatars:
    def __init__(self, fetch=None):
        self.fetch = fetch or web.get_bytes
        self.lock = threading.Lock()
        self.cache = OrderedDict()

    def get(self, url, pixels=PANEL_SIZE):
        """A data URI for the picture, or "" when it cannot be had."""
        if not url or not url.startswith("https://"):
            return ""
        key = "%s|%d" % (url, pixels)
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
        try:
            kind, data = self.fetch(sized(url, pixels))
        except Exception:
            data, kind = b"", ""
        found = data_uri(kind, data) if data and len(data) <= MAX_BYTES \
            and kind.startswith("image/") else ""
        with self.lock:
            self.cache[key] = found
            while len(self.cache) > KEEP:
                self.cache.popitem(last=False)
        return found

    def many(self, urls):
        return {url: self.get(url) for url in list(urls)[:40]}
