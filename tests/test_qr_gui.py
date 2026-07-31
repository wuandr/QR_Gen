import tkinter as tk
import unittest
from pathlib import Path
from tkinter import font as tkfont
from unittest.mock import patch

from PIL import Image

from i18n import LANGUAGES
from qr_core import QRGenerationError, QRGenerationResult
from qr_gui import (
    CJK_FONT_CANDIDATES,
    DEFAULT_SIZE,
    default_filename,
    normalise_url,
    QRGeneratorApp,
)


class PureHelperTests(unittest.TestCase):
    """No display needed — these run everywhere, including headless CI."""

    def test_bare_domain_gets_a_scheme(self) -> None:
        self.assertEqual(normalise_url("example.com"), "https://example.com")
        self.assertEqual(normalise_url("example.com/path"), "https://example.com/path")

    def test_existing_scheme_is_left_alone(self) -> None:
        self.assertEqual(normalise_url("https://example.com"), "https://example.com")
        self.assertEqual(normalise_url("ftp://example.com"), "ftp://example.com")

    def test_free_text_is_never_rewritten(self) -> None:
        self.assertEqual(normalise_url("hello world"), "hello world")
        self.assertEqual(normalise_url("  "), "")

    def test_default_filename_is_derived_from_the_host(self) -> None:
        self.assertEqual(default_filename("https://example.com/flyer", "png"), "qr-example-com.png")
        self.assertEqual(default_filename("https://example.com", "jpeg"), "qr-example-com.jpg")

    def test_default_filename_stays_ascii(self) -> None:
        name = default_filename("https://例子.測試", "png")
        self.assertTrue(name.isascii(), name)
        self.assertTrue(name.endswith(".png"))


class QRGuiTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"GUI tests require a display: {exc}")
        self.root.withdraw()
        # Pin the language and never touch the user's real config file.
        patcher = patch("qr_gui.load_language", return_value="en")
        patcher.start()
        self.addCleanup(patcher.stop)
        saver = patch("qr_gui.save_language")
        self.save_language = saver.start()
        self.addCleanup(saver.stop)

        self.app = QRGeneratorApp(self.root)
        self.t = self.app.tr.t
        self.root.update_idletasks()

    def tearDown(self) -> None:
        self.app.destroy()
        self.root.destroy()

    def _banner(self) -> str:
        return self.app.banner_label.cget("text")

    @staticmethod
    def _is_visible(widget) -> bool:
        return bool(widget.winfo_manager())

    # ------------------------------------------------------------- defaults

    def test_window_defaults(self) -> None:
        self.assertEqual(self.root.title(), self.t("app.title"))
        self.assertEqual(self.app.format_var.get(), "png")
        self.assertEqual(self.app.style_var.get(), "square")
        self.assertEqual(self.app.size_var.get(), DEFAULT_SIZE)
        self.assertEqual(self.app.overlay_path_var.get(), "")

    def test_save_is_available_from_the_start(self) -> None:
        """The old Preview-before-Save gate is gone; Save must never be disabled."""
        self.assertNotIn("disabled", self.app.save_button.state())

    def test_empty_state_prompts_for_a_url(self) -> None:
        self.assertIn(self.t("status.empty"), self._banner())
        self.assertEqual(self.app.preview_label.cget("text"), self.t("preview.placeholder"))

    def test_minimum_size_is_derived_from_content(self) -> None:
        width, height = self.root.minsize()
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)

    def test_labels_wrap_to_the_available_width(self) -> None:
        """M3: fixed wraplengths clipped text at the window's own minimum size."""
        label = self.app.url_hint
        QRGeneratorApp._wrap_to(300, label)
        self.assertEqual(int(label.cget("wraplength")), 300)

    def test_wrapping_is_not_driven_by_the_label_itself(self) -> None:
        """A label's wraplength sets its requested width, so measuring the label
        would feed back into the layout and loop forever."""
        self.assertEqual(self.app.url_hint.bind("<Configure>"), "")
        self.assertEqual(self.app.banner_label.bind("<Configure>"), "")

    def test_revealing_the_saved_file_does_not_relayout_forever(self) -> None:
        """Regression: gridding the reveal button resized the banner, which
        rewrapped it, which resized it again — the window froze."""
        self.app.reveal_button.grid()
        self.root.update()
        self.app.reveal_button.grid_remove()
        self.root.update()

    # ---------------------------------------------------------- disclosure

    def test_rounding_is_replaced_by_a_reason_for_square(self) -> None:
        self.assertFalse(self._is_visible(self.app.rounding_frame))
        self.assertTrue(self._is_visible(self.app.rounding_reason))
        self.assertEqual(self.app.rounding_reason.cget("text"), self.t("field.rounding.na_square"))

    def test_rounding_appears_for_styles_that_use_it(self) -> None:
        self.app.style_var.set("rounded")
        self.root.update_idletasks()
        self.assertTrue(self._is_visible(self.app.rounding_frame))
        self.assertFalse(self._is_visible(self.app.rounding_reason))

    def test_svg_disables_styling_and_explains_why(self) -> None:
        self.app.style_var.set("rounded")
        self.app.format_var.set("svg")
        self.root.update_idletasks()

        self.assertIn("disabled", self.app.style_buttons[0].state())
        self.assertIn("disabled", self.app.logo_choose_button.state())
        self.assertEqual(self.app.style_reason.cget("text"), self.t("field.rounding.na_svg"))
        self.assertEqual(self.app.logo_reason.cget("text"), self.t("logo.na_svg"))
        self.assertFalse(self._is_visible(self.app.rounding_frame))

    def test_svg_reason_is_stated_once_not_twice(self) -> None:
        """Regression: the Look section and the rounding row both printed
        'SVG files are always square', one under the other."""
        self.app.format_var.set("svg")
        self.root.update_idletasks()

        message = self.t("field.rounding.na_svg")
        showing = [
            name
            for name in ("style_reason", "rounding_reason", "logo_reason")
            if self._is_visible(getattr(self.app, name))
            and getattr(self.app, name).cget("text") == message
        ]
        self.assertEqual(showing, ["style_reason"])

    def test_rounding_row_is_empty_for_svg(self) -> None:
        self.app.style_var.set("rounded")
        self.app.format_var.set("svg")
        self.root.update_idletasks()
        self.assertFalse(self._is_visible(self.app.rounding_frame))
        self.assertFalse(self._is_visible(self.app.rounding_reason))

    def test_format_hint_follows_the_selection(self) -> None:
        self.assertEqual(self.app.format_hint.cget("text"), self.t("format.png.hint"))
        self.app.format_var.set("svg")
        self.root.update_idletasks()
        self.assertEqual(self.app.format_hint.cget("text"), self.t("format.svg.hint"))

    # --------------------------------------------------------------- input

    def test_scheme_hint_appears_for_a_bare_domain(self) -> None:
        self.app.url_var.set("example.com")
        self.root.update_idletasks()
        self.assertEqual(
            self.app.url_hint.cget("text"),
            self.t("field.url.hint_scheme", url="https://example.com"),
        )

    def test_no_scheme_hint_when_the_url_is_already_complete(self) -> None:
        self.app.url_var.set("https://example.com")
        self.root.update_idletasks()
        self.assertEqual(self.app.url_hint.cget("text"), "")

    def test_start_over_keeps_the_url_and_resets_the_rest(self) -> None:
        self.app.url_var.set("https://example.com")
        self.app.style_var.set("dot")
        self.app.size_var.set("large")
        self.app.format_var.set("svg")
        self.app.reset_defaults()

        self.assertEqual(self.app.url_var.get(), "https://example.com")
        self.assertEqual(self.app.style_var.get(), "square")
        self.assertEqual(self.app.size_var.get(), DEFAULT_SIZE)
        self.assertEqual(self.app.format_var.get(), "png")

    # -------------------------------------------------------------- render

    def test_typing_schedules_one_render_not_many(self) -> None:
        for text in ("h", "ht", "http", "https://example.com"):
            self.app.url_var.set(text)
        self.assertIsNotNone(self.app._pending_render)

    def test_clearing_the_url_cancels_the_pending_render(self) -> None:
        self.app.url_var.set("https://example.com")
        self.app.url_var.set("")
        self.assertIsNone(self.app._pending_render)
        self.assertIn(self.t("status.empty"), self._banner())

    def test_stale_render_results_are_discarded(self) -> None:
        self.app._job_id = 7
        stale = QRGenerationResult(
            output_path=None,
            output_format="png",
            preview_image=Image.new("RGB", (40, 40), "white"),
            pixel_size=(40, 40),
        )
        self.app._queue.put(("render_ok", 6, (stale, True)))
        self.app._process_queue()

        self.assertIsNone(self.app._readout)
        self.assertEqual(self.app.preview_label.cget("text"), self.t("preview.placeholder"))

    def test_current_render_result_is_applied(self) -> None:
        self.app._job_id = 7
        # Previews always render at PREVIEW_BOX_SIZE; 330px is a short URL.
        fresh = QRGenerationResult(
            output_path=None,
            output_format="png",
            preview_image=Image.new("RGB", (40, 40), "white"),
            pixel_size=(330, 330),
        )
        self.app._queue.put(("render_ok", 7, (fresh, True)))
        self.app._process_queue()

        self.assertEqual(
            self.app.size_readout.cget("text"),
            self.t("size.readout", format=self.t("format.png"), w=660, h=660),
        )
        self.assertIn(self.t("status.scan_ok"), self.app.scan_badge.cget("text"))
        self.assertIn(self.t("status.ready"), self._banner())

    def test_readout_reports_the_save_size_not_the_preview_size(self) -> None:
        """H4: the output size must be stated, and previews render smaller than
        they save, so the number has to be scaled up from the preview."""
        preview = QRGenerationResult(
            output_path=None,
            output_format="png",
            preview_image=Image.new("RGB", (40, 40), "white"),
            pixel_size=(330, 330),
        )
        for size, expected in (("small", 330), ("medium", 660), ("large", 1320)):
            with self.subTest(size=size):
                self.app.size_var.set(size)
                self.app._job_id += 1
                self.app._queue.put(("render_ok", self.app._job_id, (preview, True)))
                self.app._process_queue()
                self.assertEqual(
                    self.app.size_readout.cget("text"),
                    self.t("size.readout", format=self.t("format.png"), w=expected, h=expected),
                )

    def test_previews_render_at_a_fixed_small_size(self) -> None:
        """The decode check runs on every candidate placement, so previewing at
        Large would make the logo path needlessly slow."""
        self.app.size_var.set("large")
        self.assertEqual(self.app._build_request(output_path=None, for_preview=True).box_size, 10)
        self.assertEqual(self.app._build_request(output_path=Path("/tmp/x.png")).box_size, 40)

    def test_unscannable_render_warns(self) -> None:
        self.app._job_id = 1
        result = QRGenerationResult(
            output_path=None,
            output_format="png",
            preview_image=Image.new("RGB", (40, 40), "white"),
            pixel_size=(40, 40),
        )
        self.app._queue.put(("render_ok", 1, (result, False)))
        self.app._process_queue()
        self.assertIn(self.t("status.scan_warn"), self.app.scan_badge.cget("text"))

    def test_engine_errors_are_shown_in_our_own_words(self) -> None:
        self.app._job_id = 1
        self.app._queue.put(
            ("render_error", 1, QRGenerationError("Failed to open image 'x'", code="image_unreadable"))
        )
        self.app._process_queue()
        self.assertIn(self.t("error.bad_image"), self._banner())

    def test_unmapped_engine_errors_fall_back_to_a_generic_message(self) -> None:
        self.app._job_id = 1
        self.app._queue.put(("render_error", 1, QRGenerationError("boom", code="something_new")))
        self.app._process_queue()
        self.assertIn("boom", self._banner())

    # ---------------------------------------------------------------- save

    def test_saving_without_a_url_asks_for_one(self) -> None:
        self.app.url_var.set("")
        with patch("qr_gui.filedialog.asksaveasfilename") as dialog:
            self.app.start_save()
        dialog.assert_not_called()
        self.assertIn(self.t("error.no_url"), self._banner())

    def test_save_does_not_require_a_preview_first(self) -> None:
        """H1: Save used to be gated behind a successful Preview click."""
        self.app.url_var.set("https://example.com")
        with patch("qr_gui.filedialog.asksaveasfilename", return_value="") as dialog:
            self.app.start_save()
        dialog.assert_called_once()
        self.assertIn(self.t("status.save_cancelled"), self._banner())

    def test_save_dialog_is_prefilled(self) -> None:
        self.app.url_var.set("example.com")
        with patch("qr_gui.filedialog.asksaveasfilename", return_value="") as dialog:
            self.app.start_save()
        self.assertEqual(dialog.call_args.kwargs["initialfile"], "qr-example-com.png")

    def test_chosen_format_wins_over_a_conflicting_extension(self) -> None:
        """H3: the typed extension used to silently decide the output format."""
        self.app.url_var.set("https://example.com")
        self.app.format_var.set("png")
        captured = {}

        def fake_generate(request):
            captured["request"] = request
            return QRGenerationResult(
                output_path=Path(request.output_path), output_format="png", pixel_size=(660, 660)
            )

        with patch("qr_gui.filedialog.asksaveasfilename", return_value="/tmp/code.svg"):
            with patch("qr_gui.generate_qr_file", side_effect=fake_generate):
                self.app.start_save()
                self.app._save_thread.join(timeout=5)
                self.app._process_queue()

        self.assertEqual(Path(captured["request"].output_path).suffix, ".png")
        self.assertEqual(captured["request"].output_format, "png")
        self.assertIn(self.t("notice.format_corrected", format=self.t("format.png")), self._banner())

    def test_jpg_extension_is_accepted_for_jpeg(self) -> None:
        self.app.url_var.set("https://example.com")
        self.app.format_var.set("jpeg")
        captured = {}

        def fake_generate(request):
            captured["request"] = request
            return QRGenerationResult(
                output_path=Path(request.output_path), output_format="jpeg", pixel_size=(660, 660)
            )

        with patch("qr_gui.filedialog.asksaveasfilename", return_value="/tmp/code.jpg"):
            with patch("qr_gui.generate_qr_file", side_effect=fake_generate):
                self.app.start_save()
                self.app._save_thread.join(timeout=5)
                self.app._process_queue()

        self.assertEqual(Path(captured["request"].output_path).suffix, ".jpg")
        self.assertNotIn(self.t("notice.format_corrected", format="JPEG"), self._banner())

    def test_selected_size_reaches_the_engine(self) -> None:
        self.app.url_var.set("https://example.com")
        self.app.size_var.set("large")
        request = self.app._build_request(output_path=None)
        self.assertEqual(request.box_size, 40)

    # ------------------------------------------------------------ language

    def test_language_switcher_is_in_the_window(self) -> None:
        """The menu bar lives at the top of the screen on macOS, so a menu-only
        switcher is undiscoverable. There must be one in the window itself."""
        self.assertTrue(self._is_visible(self.app.language_combo))
        self.assertEqual(set(self.app.language_combo.cget("values")), set(LANGUAGES.values()))
        self.assertEqual(self.app.language_display_var.get(), LANGUAGES["en"])

    def test_selecting_in_the_combobox_switches_language(self) -> None:
        self.app.language_display_var.set(LANGUAGES["zh_TW"])
        self.app._on_language_selected()
        self.root.update_idletasks()

        self.assertEqual(self.app.tr.language, "zh_TW")
        self.assertEqual(self.app.save_button.cget("text"), self.app.tr.t("button.save"))

    def test_both_switchers_stay_in_step(self) -> None:
        self.app.set_language("zh_TW")
        self.assertEqual(self.app.language_var.get(), "zh_TW")
        self.assertEqual(self.app.language_display_var.get(), LANGUAGES["zh_TW"])

    def test_menu_bar_cascades_are_labelled_and_translated(self) -> None:
        menubar = self.app._menubar

        def labels() -> list[str]:
            last = menubar.index("end")
            return [
                menubar.entrycget(i, "label")
                for i in range(last + 1)
                if menubar.type(i) == "cascade"
            ]

        self.assertEqual(labels(), [self.t("menu.file"), self.t("menu.language"), self.t("menu.help")])
        self.app.set_language("zh_TW")
        translated = self.app.tr.t
        self.assertEqual(
            labels(),
            [translated("menu.file"), translated("menu.language"), translated("menu.help")],
        )

    def test_cascades_are_found_by_menu_not_by_a_stored_index(self) -> None:
        """macOS inserts its own application menu, shifting build-time indices."""
        for menu, _string_id in self.app._cascade_menus:
            self.assertIsNotNone(self.app._cascade_index(menu))

    # ---------------------------------------------------------------- fonts

    def test_latin_languages_keep_the_platform_font(self) -> None:
        self.assertIsNone(self.app.font_family_for_language("en"))

    def test_cjk_languages_get_a_font_that_covers_the_script(self) -> None:
        """Tk draws missing glyphs as boxes rather than falling back."""
        family = self.app.font_family_for_language("zh_TW")
        if family is None:
            self.skipTest("no CJK font installed on this machine")
        self.assertIn(family, CJK_FONT_CANDIDATES[self.app._platform_key()])
        self.assertIn(family, tkfont.families(self.app))

    def test_switching_away_from_cjk_restores_the_default_font(self) -> None:
        original = tkfont.nametofont("TkDefaultFont").cget("family")
        self.app.set_language("zh_TW")
        self.app.set_language("en")
        self.assertEqual(tkfont.nametofont("TkDefaultFont").cget("family"), original)

    def test_disclosure_text_follows_the_language(self) -> None:
        """Regression: reason labels are written imperatively by
        _apply_disclosure, so they kept the language they were written in.
        Reproduced by selecting SVG and then switching language."""
        self.app.format_var.set("svg")
        self.root.update_idletasks()
        self.app.set_language("zh_TW")
        self.root.update_idletasks()

        translated = self.app.tr.t
        self.assertEqual(self.app.style_reason.cget("text"), translated("field.rounding.na_svg"))
        self.assertEqual(self.app.logo_reason.cget("text"), translated("logo.na_svg"))
        self.assertEqual(self.app.format_hint.cget("text"), translated("format.svg.hint"))

    def test_square_rounding_reason_follows_the_language(self) -> None:
        self.app.set_language("zh_TW")
        self.root.update_idletasks()
        self.assertEqual(
            self.app.rounding_reason.cget("text"), self.app.tr.t("field.rounding.na_square")
        )

    def test_size_hint_stays_blank_for_svg_across_a_language_change(self) -> None:
        """The hint had two owners — a binding and _apply_disclosure — so the
        binding restored text that SVG had deliberately cleared."""
        self.app.format_var.set("svg")
        self.root.update_idletasks()
        self.assertEqual(self.app.size_hint.cget("text"), "")

        self.app.set_language("zh_TW")
        self.root.update_idletasks()
        self.assertEqual(self.app.size_hint.cget("text"), "")

    def test_preview_note_follows_the_language(self) -> None:
        self.app.set_language("zh_TW")
        self.root.update_idletasks()
        self.assertEqual(
            self.app.preview_label.cget("text"), self.app.tr.t("preview.placeholder")
        )

    def test_readout_format_name_is_not_frozen_at_render_time(self) -> None:
        """Deferred state stores a StringId, not an already-translated string."""
        self.app._job_id = 1
        result = QRGenerationResult(
            output_path=None,
            output_format="png",
            preview_image=Image.new("RGB", (40, 40), "white"),
            pixel_size=(330, 330),
        )
        self.app._queue.put(("render_ok", 1, (result, True)))
        self.app._process_queue()

        self.app.set_language("zh_TW")
        translated = self.app.tr.t
        self.assertEqual(
            self.app.size_readout.cget("text"),
            translated("size.readout", format=translated("format.png"), w=660, h=660),
        )

    def test_switching_language_retranslates_the_interface(self) -> None:
        english_save = self.app.save_button.cget("text")
        self.app.set_language("zh_TW")
        self.root.update_idletasks()

        self.assertNotEqual(self.app.save_button.cget("text"), english_save)
        self.assertEqual(self.app.save_button.cget("text"), self.app.tr.t("button.save"))
        self.assertEqual(self.root.title(), self.app.tr.t("app.title"))
        self.save_language.assert_called_with("zh_TW")

    def test_switching_language_retranslates_live_state(self) -> None:
        self.app.url_var.set("example.com")
        self.app.set_language("zh_TW")
        self.root.update_idletasks()

        self.assertIn(self.app.tr.t("status.empty"), self.app.banner_label.cget("text"))
        self.assertEqual(
            self.app.url_hint.cget("text"),
            self.app.tr.t("field.url.hint_scheme", url="https://example.com"),
        )

    def test_language_choice_is_remembered(self) -> None:
        window = tk.Toplevel(self.root)
        window.withdraw()
        with patch("qr_gui.load_language", return_value="zh_TW"):
            app = QRGeneratorApp(window)
        try:
            self.assertEqual(app.tr.language, "zh_TW")
            self.assertEqual(window.title(), app.tr.t("app.title"))
        finally:
            app.destroy()
            window.destroy()


if __name__ == "__main__":
    unittest.main()
