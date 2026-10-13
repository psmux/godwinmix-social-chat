"""Settings, and the rule that a key is never written down, logged or shown whole."""
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest

import helpers
from social_chat import redact, rpc, seal, vault
from social_chat.settings import Settings, SettingsError


class Folder(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="social-chat-test-")

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)
        redact.forget_all()


class Secrets(Folder):
    def test_a_sealed_key_is_opened_and_kept(self):
        s = Settings(self.folder)
        changed = s.update({"youtube_api_key": {"sealed": seal.seal(seal.public_hex(), "AIzaSyREALkey12345")}})
        self.assertEqual(changed, ["youtube_api_key"])
        self.assertEqual(s.values["youtube_api_key"], "AIzaSyREALkey12345")
        self.assertEqual(Settings(self.folder).values["youtube_api_key"], "AIzaSyREALkey12345")

    def test_a_plain_key_is_refused_before_anything_changes(self):
        s = Settings(self.folder)
        with self.assertRaises(SettingsError) as refused:
            s.update({"twitch_channels": "ours", "facebook_page_token": "EAAplaintext"})
        self.assertIn("session log", str(refused.exception))
        self.assertEqual(s.values["twitch_channels"], "")

    def test_a_key_sealed_for_another_process_is_refused(self):
        other = seal.seal(format(pow(2, 12345, seal.P), "x"), "x")
        other["pub"] = format(pow(2, 99, seal.P), "x")
        with self.assertRaises(SettingsError):
            Settings(self.folder).update({"webhook_secret": {"sealed": other}})

    def test_empty_keeps_and_null_forgets(self):
        s = Settings(self.folder)
        s.update({"webhook_secret": {"sealed": seal.seal(seal.public_hex(), "keep-me-please")}})
        self.assertEqual(s.update({"webhook_secret": ""}), [])
        self.assertEqual(s.update({"webhook_secret": None}), ["webhook_secret"])
        self.assertEqual(s.values["webhook_secret"], "")

    def test_the_view_masks_every_key(self):
        s = Settings(self.folder)
        s.update({"youtube_api_key": {"sealed": seal.seal(seal.public_hex(), "AIzaSyREALkey12345")}})
        shown = s.view()
        self.assertEqual(shown["youtube_api_key"], "stored, ending 2345")
        self.assertNotIn("AIzaSyREALkey12345", json.dumps(shown))

    def test_the_file_never_holds_a_key_in_the_clear_on_windows(self):
        s = Settings(self.folder)
        s.update({"facebook_page_token": {"sealed": seal.seal(seal.public_hex(), "EAAsecretTOKEN999")}})
        with open(os.path.join(self.folder, "settings.json"), encoding="utf-8") as f:
            raw = f.read()
        if vault.available():
            self.assertNotIn("EAAsecretTOKEN999", raw)
            self.assertIn("dpapi:", raw)
        else:
            self.assertEqual(os.stat(os.path.join(self.folder, "settings.json")).st_mode & 0o077, 0)

    def test_a_key_in_a_log_line_or_an_error_is_hidden(self):
        s = Settings(self.folder)
        s.update({"youtube_api_key": {"sealed": seal.seal(seal.public_hex(), "AIzaSyLEAKYkey777")}})
        out = io.StringIO()
        rpc.use_stream(out)
        try:
            rpc.log("error", redact.text("GET https://x/?key=AIzaSyLEAKYkey777 failed"))
        finally:
            rpc.use_stream(__import__("sys").stderr)
        self.assertNotIn("AIzaSyLEAKYkey777", out.getvalue())
        self.assertIn("[hidden]", redact.text("https://graph.facebook.com/x?access_token=EAAunknown&a=1"))


class Precedence(Folder):
    def test_the_mixer_wins_only_when_its_value_changed(self):
        s = Settings(self.folder)
        s.take_mixer({"twitch_channels": "from-config"})
        self.assertEqual(s.values["twitch_channels"], "from-config")
        s.update({"twitch_channels": "from-panel"})
        again = Settings(self.folder)
        again.take_mixer({"twitch_channels": "from-config"})
        self.assertEqual(again.values["twitch_channels"], "from-panel", "the panel's newer value is kept")
        again.take_mixer({"twitch_channels": "edited-in-config"})
        self.assertEqual(again.values["twitch_channels"], "edited-in-config")

    def test_the_mixers_sealed_placeholder_is_ignored(self):
        s = Settings(self.folder)
        s.take_mixer({"youtube_api_key": "__secret__", "keep": "800"})
        self.assertEqual(s.values["youtube_api_key"], "")
        self.assertEqual(s.values["keep"], 800)


class PanelHalf(unittest.TestCase):
    """The page seals with ui/seal.js; this process must open what it makes."""

    def test_the_pages_seal_opens_here(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        script = os.path.join(helpers.HERE, "seal_node.mjs")
        for text in ("AIzaSy-ordinary-key", "", "ключ \U0001f511" * 20):
            out = subprocess.run([node, script, seal.public_hex(), text], capture_output=True,
                                 text=True, encoding="utf-8", check=True).stdout
            self.assertEqual(seal.open_sealed(json.loads(out)), text)


if __name__ == "__main__":
    unittest.main()
