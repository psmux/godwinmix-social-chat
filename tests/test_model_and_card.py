"""One comment's shape, the question test, and the words cut for the on air card."""
import unittest

import helpers  # noqa: F401
from social_chat import card
from social_chat.model import comment, is_question, parse_time


class Model(unittest.TestCase):
    def test_questions(self):
        for text in ("what camera is that", "How long have you been streaming?",
                     "Q: will there be a recording", "is it live yet", "a question？"):
            self.assertTrue(is_question(text), text)
        for text in ("hello", "what", "great stream", "Is", ""):
            self.assertFalse(is_question(text), text)

    def test_times_in_every_form_the_platforms_use(self):
        expected = 1791914400000.0
        for value in ("2026-10-13T18:00:00Z", "2026-10-13T18:00:00+0000", "2026-10-13T18:00:00.000000+00:00",
                      "2026-10-13T19:00:00+01:00", 1791914400, 1791914400000, "1791914400000"):
            self.assertAlmostEqual(parse_time(value), expected, msg=repr(value))
        self.assertAlmostEqual(parse_time("2026-10-13T18:00:00.1234567Z"), expected + 123.456)
        self.assertEqual(parse_time("not a time", fallback=5.0), 5.0)

    def test_control_characters_and_length_are_cleaned(self):
        item = comment("x", "1", "  Sam\x00  ", "a\x07b" + "c" * 3000)
        self.assertEqual(item["author"], "Sam")
        self.assertTrue(item["text"].startswith("a b"))
        self.assertEqual(len(item["text"]), 2000)
        self.assertEqual(comment("x", "2", "", "hi")["author"], "someone")


class Card(unittest.TestCase):
    def test_words_wrap_at_word_boundaries(self):
        self.assertEqual(card.wrap("one two three four", 2, 9), ["one two", "three\u2026"])
        self.assertEqual(card.wrap("short", 3, 40), ["short", "", ""])
        self.assertEqual(card.wrap("", 2, 10), ["", ""])

    def test_a_long_word_is_cut_rather_than_overflowing(self):
        lines = card.wrap("a" * 100, 2, 10)
        self.assertEqual(lines[0], "a" * 9 + "\u2026")

    def test_card_fields_fill_every_template_field(self):
        item = comment("youtube", "1", "Priya Natarajan", "Can you show the mixer again? " * 6,
                       amount="$5.00")
        fields = card.fields(item, "card")
        self.assertEqual(set(fields), {"author", "platform", "platform_colour", "tag", "line1", "line2",
                                       "line3", "initials", "avatar"})
        self.assertEqual(fields["initials"], "PN")
        self.assertEqual(fields["tag"], "$5.00")
        self.assertEqual(fields["platform_colour"], "#ff0033")
        self.assertTrue(fields["line3"].endswith("\u2026"))
        self.assertTrue(fields["avatar"].startswith("data:image/png"))

    def test_a_question_is_tagged_and_the_strap_has_one_line(self):
        item = comment("twitch", "1", "pixel_otter", "what camera is that?")
        fields = card.fields(item, "strap")
        self.assertEqual(set(fields), {"author", "platform", "platform_colour", "tag", "message"})
        self.assertEqual(fields["tag"], "QUESTION")

    def test_a_picture_too_big_for_a_field_is_left_out(self):
        item = comment("youtube", "1", "A", "b")
        self.assertEqual(card.fields(item, "card", "data:image/jpeg;base64," + "A" * 3000)["avatar"],
                         card.CLEAR_PIXEL)
        small = "data:image/jpeg;base64," + "A" * 100
        self.assertEqual(card.fields(item, "card", small)["avatar"], small)

    def test_the_template_fields_match_what_card_fields_sends(self):
        import os
        import re
        for style in ("card", "strap"):
            path = os.path.join(helpers.ROOT, "graphics", card.STYLES[style][0])
            with open(path, encoding="utf-8") as f:
                declared = set(re.findall(r'gmx:field name="([a-z0-9_]+)"', f.read()))
            sent = set(card.fields(comment("x", "1", "a", "b"), style))
            self.assertTrue(sent <= declared, "%s sends %s" % (style, sent - declared))

    def test_the_template_address_is_absolute_with_forward_slashes(self):
        uri = card.template_uri("C:\\plugins\\social-chat\\1.0.0", "card")
        self.assertTrue(uri.startswith("template:"))
        self.assertTrue(uri.endswith("/graphics/comment-card.svg"))
        self.assertNotIn("\\", uri)


if __name__ == "__main__":
    unittest.main()
