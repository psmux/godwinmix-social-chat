"""The tools the panel and agents call: moderation, the card and the panel files."""
import os
import shutil
import tempfile
import unittest

import helpers
from social_chat import panel_files, tools
from social_chat.model import comment
from social_chat.service import Chat


class Tools(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="social-chat-tools-")
        self.chat = Chat(helpers.ROOT, self.folder)

    def tearDown(self):
        self.chat.stop()
        shutil.rmtree(self.folder, ignore_errors=True)

    def add(self, native, author, text, author_id=None):
        item = comment("twitch", native, author, text, author_id=author_id or author)
        self.chat.sink.add(item)
        return item["id"]

    def test_ban_removes_an_author_and_keeps_them_out_after_a_restart(self):
        spam = self.add("1", "spammer", "buy followers")
        self.add("2", "fine", "hello")
        tools.call(self.chat, "ban", {"id": spam, "banned": True})
        self.assertEqual([c["author"] for c in self.chat.hub.snapshot()], ["fine"])
        self.add("3", "spammer", "buy more")
        self.assertEqual(len(self.chat.hub.snapshot()), 1)
        again = Chat(helpers.ROOT, self.folder)
        self.assertTrue(again.moderation.is_banned({"platform": "twitch", "author_id": "spammer"}))
        key = again.moderation.view()["banned"][0]["key"]
        tools.call(again, "ban", {"key": key, "banned": False})
        self.assertEqual(again.moderation.view()["banned"], [])

    def test_a_pin_outlives_the_comment_scrolling_off(self):
        first = self.add("p", "someone", "pin me")
        tools.call(self.chat, "pin", {"id": first})
        self.chat.hub.keep = 50
        for n in range(80):
            self.add("n%d" % n, "busy", "x")
        self.assertIsNone(self.chat.hub.get(first))
        pins = tools.call(self.chat, "comments", {"after": 0})["moderation"]["pins"]
        self.assertEqual([p["id"] for p in pins], [first])
        card = tools.call(self.chat, "card_fields", {"id": first, "style": "card"})
        self.assertEqual(card["fields"]["line1"], "pin me")

    def test_hide_and_on_air_are_reported_to_every_panel(self):
        cid = self.add("h", "someone", "what is this?")
        tools.call(self.chat, "hide", {"id": cid})
        tools.call(self.chat, "card_fields", {"id": cid})
        state = tools.call(self.chat, "comments", {"after": 0})
        self.assertEqual(state["moderation"]["hidden"], [cid])
        self.assertEqual(state["onair"]["id"], cid)
        tools.call(self.chat, "card_off", {})
        self.assertIsNone(tools.call(self.chat, "comments", {"after": 0})["onair"])

    def test_an_unknown_comment_or_tool_says_what_to_do(self):
        with self.assertRaises(tools.ToolError) as missing:
            tools.call(self.chat, "pin", {"id": "twitch:gone"})
        self.assertIn("Call comments", str(missing.exception))
        with self.assertRaises(tools.ToolError) as unknown:
            tools.call(self.chat, "social-chat/teleport", {})
        self.assertIn("comments", unknown.exception.data["tools"])

    def test_every_tool_in_the_manifest_exists_and_has_a_schema(self):
        import re
        with open(os.path.join(helpers.ROOT, "gmx-plugin.toml"), encoding="utf-8") as f:
            manifest = f.read()
        names = re.findall(r'^name = "([a-z_]+)"', manifest, re.M)
        self.assertEqual(sorted(names), sorted(tools.TOOLS))
        for path in re.findall(r'^input = "([^"]+)"', manifest, re.M):
            self.assertTrue(os.path.isfile(os.path.join(helpers.ROOT, path)), path)

    def test_status_names_the_next_step_for_a_platform_not_set_up(self):
        status = {s["platform"]: s for s in tools.call(self.chat, "status", {})["statuses"]}
        self.assertEqual(status["youtube"]["state"], "off")
        self.assertIn("API key", status["youtube"]["next"])
        self.assertIn("paid", status["x"]["next"])


class PanelFiles(unittest.TestCase):
    def test_the_panel_is_copied_up_out_of_a_version_folder_only(self):
        plugins = tempfile.mkdtemp(prefix="social-chat-plugins-")
        try:
            root = os.path.join(plugins, "social-chat", "1.0.0")
            shutil.copytree(os.path.join(helpers.ROOT, "ui"), os.path.join(root, "ui"))
            shutil.copy(os.path.join(helpers.ROOT, "gmx-plugin.toml"), root)
            self.assertGreater(panel_files.mirror(root), 3)
            self.assertTrue(os.path.isfile(os.path.join(plugins, "social-chat", "ui", "panel.html")))
            self.assertEqual(panel_files.mirror(root), 0, "nothing is written twice")
            self.assertIsNone(panel_files.target_for(helpers.ROOT), "a checkout is left alone")
        finally:
            shutil.rmtree(plugins, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
