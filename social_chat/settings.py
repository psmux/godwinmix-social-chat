"""The plugin's settings: what the mixer hands over, and what the panel saves.

Two places can set a value. The mixer's own plugin settings (the
`[plugins.social-chat]` table, with keys and tokens sealed in its secret
store) arrive in the handshake and in `configure`. The panel's Settings form
saves through the `save_settings` tool, which applies at once and is written
to `settings.json` in this plugin's data folder, readable by this user only.

When both have a value, the one changed most recently wins: the file keeps
what the mixer said last time, so a value the operator changes in the mixer
is noticed at the next start and taken, and one changed in the panel is kept.

Secrets are never logged and never answered whole; `view` shows the last four
characters at most.
"""
import json
import os
import tempfile

from . import redact, seal, vault

SENTINEL = "__secret__"

DEFAULTS = {
    "youtube_video": "",
    "youtube_api_key": "",
    "youtube_oauth_token": "",
    "youtube_client_id": "",
    "youtube_client_secret": "",
    "youtube_refresh_token": "",
    "youtube_min_poll_seconds": 5,
    "twitch_channels": "",
    "facebook_live_video": "",
    "facebook_page_token": "",
    "facebook_mode": "stream",
    "facebook_poll_seconds": 5,
    "webhook_enabled": False,
    "webhook_bind": "127.0.0.1",
    "webhook_port": 8790,
    "webhook_secret": "",
    "x_enabled": False,
    "practice_mode": False,
    "keep": 500,
    "question_colour": "#f5b301",
    "card_style": "card",
}

SECRETS = ("youtube_api_key", "youtube_oauth_token", "youtube_client_secret",
           "youtube_refresh_token", "facebook_page_token", "webhook_secret")


def data_dir():
    """Where this plugin keeps its own files, outside its install folder."""
    if os.environ.get("SOCIAL_CHAT_DATA"):
        return os.environ["SOCIAL_CHAT_DATA"]
    home = os.environ.get("GODWINMIX_HOME") or os.path.join(os.path.expanduser("~"),
                                                             ".godwinmix")
    return os.path.join(home, "plugin-data", "social-chat")


def coerce(key, value):
    """A value of the type its default has. Bad input falls back to the default."""
    default = DEFAULTS[key]
    try:
        if isinstance(default, bool):
            return value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes", "on")
        if isinstance(default, int):
            return int(float(value))
        return "" if value is None else str(value).strip()
    except (TypeError, ValueError):
        return default


class SettingsError(Exception):
    pass


def secret_of(key, value):
    """A key or token from the panel: sealed, or null to forget it."""
    if value is None:
        return None
    if isinstance(value, dict) and isinstance(value.get("sealed"), dict):
        try:
            return seal.open_sealed(value["sealed"])
        except seal.SealError as e:
            raise SettingsError("%s: %s" % (key, e)) from None
    raise SettingsError(
        "%s was sent as plain text, and the mixer writes every tool.call into its session "
        "log. Type it in the Social Chat panel's Settings, which seals it, or put it in "
        "[plugins.social-chat] in the mixer's config file." % key)


class Settings:
    def __init__(self, folder=None):
        self.folder = folder or data_dir()
        self.path = os.path.join(self.folder, "settings.json")
        self.values = dict(DEFAULTS)
        self.from_mixer = {}
        self._read()

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            saved = {}
        for key, value in (saved.get("values") or {}).items():
            if key in DEFAULTS:
                self.values[key] = coerce(key, vault.unprotect(value))
        self.from_mixer = {k: vault.unprotect(v) for k, v in (saved.get("from_mixer") or {}).items()}
        self._register()

    def take_mixer(self, params):
        """Lay the mixer's params over ours, where the mixer's value is new."""
        changed = False
        for key, value in (params or {}).items():
            if key not in DEFAULTS or value in (None, SENTINEL):
                continue
            value = coerce(key, value)
            if self.from_mixer.get(key) != value:
                self.from_mixer[key] = value
                self.values[key] = value
                changed = True
        if changed:
            self.save()
        self._register()
        return changed

    def update(self, changes):
        """Apply the panel's changes. A secret arrives sealed (`{"sealed":
        {...}}`, see seal.py), "" keeps it as it was and null forgets it.
        Answers the keys that really changed."""
        pending = {}
        for key, value in (changes or {}).items():
            if key not in DEFAULTS:
                continue
            if key in SECRETS:
                if value in ("", SENTINEL):
                    continue
                value = secret_of(key, value)  # raises before anything changes
            pending[key] = DEFAULTS[key] if value is None else coerce(key, value)
        changed = [key for key, value in pending.items() if self.values[key] != value]
        for key in changed:
            self.values[key] = pending[key]
        if changed:
            self.save()
        self._register()
        return changed

    def view(self):
        """Every value, with secrets masked, for the panel and for agents."""
        shown = dict(self.values)
        for key in SECRETS:
            shown[key] = redact.mask(self.values.get(key, ""))
        return shown

    def save(self):
        os.makedirs(self.folder, exist_ok=True)
        locked = {k: vault.protect(v) if k in SECRETS else v for k, v in self.values.items()}
        mixer = {k: vault.protect(v) if k in SECRETS else v for k, v in self.from_mixer.items()}
        body = json.dumps({"values": locked, "from_mixer": mixer}, indent=2, sort_keys=True)
        handle, temp = tempfile.mkstemp(dir=self.folder, prefix=".settings-")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as f:
                f.write(body)
            if os.name != "nt":
                os.chmod(temp, 0o600)
            os.replace(temp, self.path)
        except OSError:
            if os.path.exists(temp):
                os.remove(temp)
            raise

    def _register(self):
        for key in SECRETS:
            redact.register(self.values.get(key, ""))
