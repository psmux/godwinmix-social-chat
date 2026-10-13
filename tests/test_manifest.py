"""gmx-plugin.toml, the settings schema and the skill, against the rules in
GodwinMix's docs/reference/plugin-manifest.md. `gmx plugin test .` runs the
mixer's own validator; this catches the same mistakes with no mixer."""
import json
import os
import re
import unittest

from helpers import ROOT

try:
    import tomllib
except ImportError:  # Python 3.10
    tomllib = None

TRIPLES = {"linux-x86_64", "linux-aarch64", "linux-armv7", "macos-aarch64", "macos-x86_64",
           "windows-x86_64", "windows-aarch64"}


@unittest.skipIf(tomllib is None, "needs Python 3.11 for tomllib")
class Manifest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "gmx-plugin.toml"), "rb") as f:
            self.m = tomllib.load(f)

    def test_the_plugin_table(self):
        p = self.m["plugin"]
        self.assertRegex(p["name"], r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
        self.assertRegex(p["version"], r"^\d+\.\d+\.\d+")
        self.assertEqual(p["api"], 1)
        self.assertLessEqual(len(p["description"]), 1024)
        self.assertTrue(set(p["platforms"]) <= TRIPLES)
        self.assertEqual(p["placements"], ["sidecar"])
        self.assertTrue(os.path.isfile(os.path.join(ROOT, self.m["run"]["python"])))

    def test_the_version_matches_main_py(self):
        with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as f:
            self.assertIn('VERSION = "%s"' % self.m["plugin"]["version"], f.read())

    def test_every_path_exists(self):
        for provide in self.m["provides"]:
            for key in ("settings", "skill"):
                if key in provide:
                    self.assertTrue(os.path.isfile(os.path.join(ROOT, provide[key])), provide[key])
            if provide["kind"] == "panel":
                self.assertTrue(os.path.isfile(os.path.join(ROOT, provide["panel"]["entry"])))
        for tool in self.m["tools"]:
            self.assertIn("example", tool["description"].lower(), tool["name"])
            self.assertRegex(tool["name"], r"^[a-z][a-z0-9_]*$")
            self.assertTrue(os.path.isfile(os.path.join(ROOT, tool["input"])), tool["input"])
            hints = tool.get("annotations", {})
            self.assertFalse(hints.get("readOnlyHint") and hints.get("destructiveHint"))

    def test_the_settings_schema_gives_every_field_a_description_default_and_example(self):
        with open(os.path.join(ROOT, "schemas", "settings.json"), encoding="utf-8") as f:
            schema = json.load(f)
        from social_chat.settings import DEFAULTS, SECRETS
        self.assertEqual(set(schema["properties"]), set(DEFAULTS))
        for key, prop in schema["properties"].items():
            self.assertTrue(prop.get("description"), key)
            self.assertEqual(prop.get("default"), DEFAULTS[key], key)
            self.assertTrue(prop.get("examples"), key)
            self.assertEqual(prop.get("format") == "secret", key in SECRETS, key)

    def test_the_skill_says_when_to_use_it(self):
        with open(os.path.join(ROOT, "skills", "chat", "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        front = re.match(r"^---\n(.*?)\n---\n(.+)", text, re.S)
        self.assertIsNotNone(front)
        description = re.search(r"^description: (.+)$", front.group(1), re.M).group(1)
        self.assertLessEqual(len(description), 1024)
        self.assertRegex(description.lower(), r"use (it |this )?when")
        self.assertLess(len(front.group(2)) / 4, 5000)


if __name__ == "__main__":
    unittest.main()
