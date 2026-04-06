import tkinter as tk
import unittest

from qr_gui import QRGeneratorApp


class QRGuiTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"GUI tests require a display: {exc}")
        self.root.withdraw()
        self.app = QRGeneratorApp(self.root)
        self.root.update_idletasks()

    def tearDown(self) -> None:
        self.app.destroy()
        self.root.destroy()

    def test_window_defaults(self) -> None:
        self.assertEqual(self.root.title(), "QR Generator")
        self.assertEqual(self.app.format_var.get(), "PNG")
        self.assertEqual(self.app.style_var.get(), "square")
        self.assertEqual(self.app.preview_button.cget("text"), "Preview")
        self.assertEqual(str(self.app.save_button.cget("state")), "disabled")

    def test_softness_control_changes_with_format_and_style(self) -> None:
        self.assertEqual(str(self.app.softness_entry.cget("state")), "disabled")

        self.app.style_var.set("rounded")
        self.root.update_idletasks()
        self.assertEqual(str(self.app.softness_entry.cget("state")), "normal")

        self.app.format_var.set("SVG")
        self.root.update_idletasks()
        self.assertEqual(str(self.app.softness_entry.cget("state")), "disabled")
        self.assertEqual(str(self.app.style_combo.cget("state")), "disabled")

    def test_empty_url_validation_message(self) -> None:
        self.app.url_var.set("")
        self.app.start_preview()
        self.assertIn("Enter a URL", self.app.status_var.get())

    def test_invalid_softness_validation_message(self) -> None:
        self.app.url_var.set("https://example.com")
        self.app.softness_var.set("not-a-number")
        self.app.start_preview()
        self.assertIn("Softness must be a number", self.app.status_var.get())

    def test_save_requires_current_preview(self) -> None:
        self.app.url_var.set("https://example.com")
        self.app.start_save()
        self.assertIn("Click Preview before saving", self.app.status_var.get())


if __name__ == "__main__":
    unittest.main()
