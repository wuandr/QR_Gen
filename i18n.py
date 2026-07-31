"""User-visible strings for the desktop app, and the machinery to translate them live.

Every string the GUI shows has a stable ID here. Widgets are bound to an ID
rather than to literal text, so switching language re-applies the whole UI
without rebuilding it.

Adding a language means adding one table to ``STRINGS`` and one entry to
``LANGUAGES``. Placeholders are named (``{url}``, ``{w}``) so translations can
reorder them freely.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

DEFAULT_LANGUAGE = "en"

# Display names stay in their own language, the usual convention for a language picker.
LANGUAGES = {
    "en": "English",
    "zh_TW": "繁體中文",
}

CONFIG_PATH = Path.home() / ".qr_generator.json"


STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # Window and menus
        "app.title": "QR Code Maker",
        "menu.file": "File",
        "menu.file.save": "Save image…",
        "menu.file.reset": "Start over",
        "menu.file.quit": "Quit",
        "menu.language": "Language",
        "menu.help": "Help",
        "menu.help.about": "About QR Code Maker",
        "dialog.about.title": "About",
        "dialog.about.body": (
            "QR Code Maker\n\n"
            "Type a web address, choose how it should look, and save the image.\n"
            "Every code is checked to make sure it still scans."
        ),
        # Web address
        "field.url.label": "Where should this code go?",
        "field.url.placeholder": "https://example.com",
        "field.url.hint_scheme": "We'll use {url}",
        # Look
        "section.look": "Look",
        "style.square": "Square",
        "style.dot": "Dots",
        "style.rounded": "Rounded",
        "style.smooth": "Smooth",
        "style.diag_rounded": "Diagonal",
        "field.rounding.label": "Corner rounding",
        "field.rounding.min": "Sharp",
        "field.rounding.max": "Round",
        "field.rounding.na_square": "The Square style has no rounded corners.",
        "field.rounding.na_svg": "SVG files are always square.",
        # Logo
        "section.logo": "Logo in the middle (optional)",
        "logo.none": "No logo",
        "logo.choose": "Choose image…",
        "logo.remove": "Remove",
        "logo.na_svg": "Logos can only be added to PNG and JPEG files.",
        # Size
        "section.size": "Size",
        "size.small": "Small",
        "size.medium": "Medium",
        "size.large": "Large",
        "size.large_hint": "Large is best for printing.",
        "size.readout": "{format} · {w} × {h} px",
        "size.readout_svg": "SVG · scales to any size",
        # File format
        "section.file": "File",
        "format.png": "PNG",
        "format.jpeg": "JPEG",
        "format.svg": "SVG",
        "format.png.hint": "Works almost everywhere.",
        "format.jpeg.hint": "Smaller file, no transparency.",
        "format.svg.hint": "Scales to any size — no logo or styling.",
        # Buttons
        "button.save": "Save image",
        "button.reset": "Start over",
        "button.reveal.darwin": "Show in Finder",
        "button.reveal.win32": "Show in Explorer",
        "button.reveal.other": "Open folder",
        # Preview
        "preview.placeholder": "Your code will appear here",
        "preview.svg": "SVG files have no preview. Save the file to see it.",
        # Status banner
        "status.empty": "Type a web address to begin.",
        "status.rendering": "Making your code…",
        "status.rendering_logo": "Adding your logo…",
        "status.scan_ok": "Scans correctly",
        "status.scan_warn": "This code may be hard to scan.",
        "status.ready": "Ready to save.",
        "status.saving": "Saving…",
        "status.saved": "Saved to {path}",
        "status.save_cancelled": "Nothing was saved.",
        # Problems
        "error.no_url": "Enter a web address first.",
        "error.bad_image": "That file isn't an image we can use. Try a PNG or JPG.",
        "error.image_missing": "We can't find that image any more. Choose another one.",
        "error.logo_too_big": (
            "We couldn't fit that logo and keep the code scannable. "
            "Try a simpler logo, or a shorter link."
        ),
        "error.folder_missing": "That folder no longer exists. Pick another place to save.",
        "error.save_failed": "We couldn't save the file. {reason}",
        "error.opencv_missing": "Logos need an extra component that isn't installed.",
        "error.generic": "Something went wrong. {reason}",
        # Notices
        "notice.format_corrected": "Saved as {format} to match your File choice.",
        "notice.logo_dropped_svg": "SVG files can't include a logo, so it wasn't added.",
        "notice.style_dropped_svg": "SVG files are always square, so the style wasn't applied.",
        "notice.image_downscaled": "Your image was large, so we scaled it to {w} × {h}.",
        # Dialogs
        "dialog.save.title": "Save QR code",
        "dialog.logo.title": "Choose a logo image",
        "filetype.images": "Images",
        "filetype.all": "All files",
    },
    # Traditional Chinese as used in Taiwan: 儲存 (not 保存), 檔案 (not 文件),
    # 網址, 資料夾, 檔案總管.
    "zh_TW": {
        # Window and menus
        "app.title": "QR Code 製作工具",
        "menu.file": "檔案",
        "menu.file.save": "儲存圖片…",
        "menu.file.reset": "重新開始",
        "menu.file.quit": "結束",
        "menu.language": "語言",
        "menu.help": "說明",
        "menu.help.about": "關於 QR Code 製作工具",
        "dialog.about.title": "關於",
        "dialog.about.body": (
            "QR Code 製作工具\n\n"
            "輸入網址、選擇外觀，然後儲存圖片。\n"
            "每個 QR Code 都會經過檢查，確認可以掃描。"
        ),
        # Web address
        "field.url.label": "這個 QR Code 要連到哪裡？",
        "field.url.placeholder": "https://example.com",
        "field.url.hint_scheme": "將使用 {url}",
        # Look
        "section.look": "外觀",
        "style.square": "方形",
        "style.dot": "圓點",
        "style.rounded": "圓角",
        "style.smooth": "平滑",
        "style.diag_rounded": "斜角",
        "field.rounding.label": "圓角程度",
        "field.rounding.min": "銳利",
        "field.rounding.max": "圓潤",
        "field.rounding.na_square": "方形樣式沒有圓角。",
        "field.rounding.na_svg": "SVG 檔案一律為方形。",
        # Logo
        "section.logo": "中央標誌（可省略）",
        "logo.none": "沒有標誌",
        "logo.choose": "選擇圖片…",
        "logo.remove": "移除",
        "logo.na_svg": "只有 PNG 和 JPEG 檔案可以加上標誌。",
        # Size
        "section.size": "尺寸",
        "size.small": "小",
        "size.medium": "中",
        "size.large": "大",
        "size.large_hint": "列印建議使用「大」。",
        "size.readout": "{format} · {w} × {h} 像素",
        "size.readout_svg": "SVG · 可縮放至任意尺寸",
        # File format
        "section.file": "檔案格式",
        "format.png": "PNG",
        "format.jpeg": "JPEG",
        "format.svg": "SVG",
        "format.png.hint": "幾乎所有地方都能使用。",
        "format.jpeg.hint": "檔案較小，不支援透明背景。",
        "format.svg.hint": "可縮放至任意尺寸 — 不支援標誌與樣式。",
        # Buttons
        "button.save": "儲存圖片",
        "button.reset": "重新開始",
        "button.reveal.darwin": "在 Finder 中顯示",
        "button.reveal.win32": "在檔案總管中顯示",
        "button.reveal.other": "開啟資料夾",
        # Preview
        "preview.placeholder": "QR Code 會顯示在這裡",
        "preview.svg": "SVG 檔案無法預覽，儲存後即可檢視。",
        # Status banner
        "status.empty": "請先輸入網址。",
        "status.rendering": "正在製作 QR Code…",
        "status.rendering_logo": "正在加入標誌…",
        "status.scan_ok": "可以正常掃描",
        "status.scan_warn": "這個 QR Code 可能不易掃描。",
        "status.ready": "可以儲存了。",
        "status.saving": "儲存中…",
        "status.saved": "已儲存至 {path}",
        "status.save_cancelled": "未儲存任何檔案。",
        # Problems
        "error.no_url": "請先輸入網址。",
        "error.bad_image": "這個檔案不是可以使用的圖片，請改用 PNG 或 JPG。",
        "error.image_missing": "找不到這張圖片了，請另外選擇一張。",
        "error.logo_too_big": "這個標誌會讓 QR Code 無法掃描，請改用簡單一點的標誌，或縮短網址。",
        "error.folder_missing": "這個資料夾已不存在，請選擇其他儲存位置。",
        "error.save_failed": "無法儲存檔案。{reason}",
        "error.opencv_missing": "加入標誌需要一個尚未安裝的元件。",
        "error.generic": "發生問題。{reason}",
        # Notices
        "notice.format_corrected": "已依照您選擇的檔案格式，儲存為 {format}。",
        "notice.logo_dropped_svg": "SVG 檔案無法加入標誌，因此沒有加入。",
        "notice.style_dropped_svg": "SVG 檔案一律為方形，因此沒有套用樣式。",
        "notice.image_downscaled": "圖片太大，已縮小為 {w} × {h}。",
        # Dialogs
        "dialog.save.title": "儲存 QR Code",
        "dialog.logo.title": "選擇標誌圖片",
        "filetype.images": "圖片",
        "filetype.all": "所有檔案",
    },
}


class _SafeDict(dict):
    """Leaves unknown placeholders intact instead of raising at render time."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class Translator:
    """Holds the current language and re-applies bound strings when it changes.

    Owned by the app rather than kept module-global so tests can create and
    discard translators without leaking bindings to destroyed widgets.
    """

    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        self._language = language if language in STRINGS else DEFAULT_LANGUAGE
        self._observers: list[Callable[[], None]] = []

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        if language not in STRINGS or language == self._language:
            return
        self._language = language
        self.refresh()

    def t(self, string_id: str, **params: object) -> str:
        table = STRINGS.get(self._language, {})
        template = table.get(string_id) or STRINGS[DEFAULT_LANGUAGE].get(string_id)
        if template is None:
            return string_id
        if not params:
            return template
        return template.format_map(_SafeDict(params))

    def observe(self, callback: Callable[[], None]) -> None:
        """Register something to re-run on every language change."""
        self._observers.append(callback)
        callback()

    def bind_call(self, setter: Callable[[str], object], string_id: str, **params: object) -> None:
        """Feed a translated string to `setter` now and on every language change."""
        self.observe(lambda: setter(self.t(string_id, **params)))

    def bind(self, widget: object, option: str, string_id: str, **params: object) -> object:
        """Keep a widget option (usually `text`) translated. Returns the widget."""
        self.bind_call(lambda text: widget.configure(**{option: text}), string_id, **params)
        return widget

    def refresh(self) -> None:
        for callback in self._observers:
            callback()

    def clear(self) -> None:
        self._observers.clear()


def load_language(path: Path = CONFIG_PATH) -> str:
    """Read the saved language, falling back to the default on any problem."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULT_LANGUAGE
    language = data.get("language") if isinstance(data, dict) else None
    return language if language in STRINGS else DEFAULT_LANGUAGE


def save_language(language: str, path: Path = CONFIG_PATH) -> None:
    """Persist the language choice. Never raises — this is a convenience, not a feature."""
    try:
        path.write_text(json.dumps({"language": language}), encoding="utf-8")
    except OSError:
        pass
