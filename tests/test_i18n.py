import re
import tempfile
import unittest
from pathlib import Path

from i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    STRINGS,
    StringId,
    Translator,
    load_language,
    save_language,
)


PLACEHOLDER = re.compile(r"\{(\w+)\}")


class CatalogueTests(unittest.TestCase):
    def test_every_language_is_listed(self) -> None:
        self.assertEqual(set(STRINGS), set(LANGUAGES))

    def test_translations_cover_every_string_id(self) -> None:
        expected = set(STRINGS[DEFAULT_LANGUAGE])
        for language, table in STRINGS.items():
            with self.subTest(language=language):
                self.assertEqual(set(table), expected)

    def test_placeholders_match_across_languages(self) -> None:
        """A translation that drops or renames a placeholder would render wrong text."""
        for string_id, template in STRINGS[DEFAULT_LANGUAGE].items():
            expected = set(PLACEHOLDER.findall(template))
            for language, table in STRINGS.items():
                with self.subTest(string_id=string_id, language=language):
                    self.assertEqual(set(PLACEHOLDER.findall(table[string_id])), expected)

    def test_no_blank_strings(self) -> None:
        for language, table in STRINGS.items():
            for string_id, text in table.items():
                with self.subTest(language=language, string_id=string_id):
                    self.assertTrue(text.strip(), f"{language}/{string_id} is empty")


class TranslatorTests(unittest.TestCase):
    def test_unknown_id_returns_the_id(self) -> None:
        self.assertEqual(Translator().t("nope.not.here"), "nope.not.here")

    def test_named_parameters_are_substituted(self) -> None:
        self.assertIn("42", Translator().t("size.readout", format="PNG", w=42, h=42))

    def test_missing_parameter_does_not_raise(self) -> None:
        self.assertIn("{path}", Translator().t("status.saved"))

    def test_string_id_parameters_are_translated_at_render_time(self) -> None:
        translator = Translator("zh_TW")
        rendered = translator.t("notice.format_corrected", format=StringId("format.png"))
        self.assertIn(STRINGS["zh_TW"]["format.png"], rendered)
        self.assertNotIn("format.png", rendered)

    def test_plain_string_parameters_are_left_alone(self) -> None:
        rendered = Translator().t("status.saved", path="format.png")
        self.assertIn("format.png", rendered)

    def test_unknown_language_falls_back_to_the_default(self) -> None:
        translator = Translator("kl_ZZ")
        self.assertEqual(translator.language, DEFAULT_LANGUAGE)
        translator.set_language("kl_ZZ")
        self.assertEqual(translator.language, DEFAULT_LANGUAGE)

    def test_bound_values_follow_the_language(self) -> None:
        seen = []
        translator = Translator("en")
        translator.bind_call(seen.append, "button.save")
        self.assertEqual(seen, [STRINGS["en"]["button.save"]])

        translator.set_language("zh_TW")
        self.assertEqual(seen[-1], STRINGS["zh_TW"]["button.save"])

    def test_clear_stops_further_updates(self) -> None:
        seen = []
        translator = Translator("en")
        translator.bind_call(seen.append, "button.save")
        translator.clear()
        translator.set_language("zh_TW")
        self.assertEqual(len(seen), 1)


class LanguagePersistenceTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.json"
            save_language("zh_TW", path)
            self.assertEqual(load_language(path), "zh_TW")

    def test_missing_or_corrupt_config_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "absent.json"
            self.assertEqual(load_language(missing), DEFAULT_LANGUAGE)

            corrupt = Path(tmpdir) / "corrupt.json"
            corrupt.write_text("not json", encoding="utf-8")
            self.assertEqual(load_language(corrupt), DEFAULT_LANGUAGE)

    def test_saving_to_an_unwritable_path_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            save_language("zh_TW", Path(tmpdir) / "no-such-dir" / "config.json")


if __name__ == "__main__":
    unittest.main()
