from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk
from urllib.parse import urlparse

from PIL import Image, ImageTk

from i18n import LANGUAGES, StringId, Translator, load_language, save_language
from qr_core import (
    BOX_SIZE_PRESETS,
    DEFAULT_SOFTNESS,
    DEFAULT_STYLE,
    QRGenerationError,
    QRGenerationResult,
    QRRequest,
    can_decode_to_url,
    generate_qr_file,
    render_qr_preview,
)


RASTER_FORMATS = ("png", "jpeg")
ALL_FORMATS = RASTER_FORMATS + ("svg",)
EXTENSIONS = {"png": ".png", "jpeg": ".jpg", "svg": ".svg"}
# Extensions we accept without correction, per format.
ACCEPTED_EXTENSIONS = {"png": {".png"}, "jpeg": {".jpg", ".jpeg"}, "svg": {".svg"}}

STYLES = ("square", "dot", "rounded", "smooth", "diag_rounded")
SOFTNESS_STYLES = {"rounded", "smooth", "diag_rounded"}

# The distinct layouts the disclosure rules can produce, as (format, style). The
# window minimum is measured against all of them, so no later selection can make
# the form taller than the space it was given. Listed rather than derived: if a
# new rule adds a taller layout, this is the one place that has to learn about it.
DISCLOSURE_LAYOUTS = (
    ("png", "square"),    # rounding slider replaced by a one-line reason
    ("png", "rounded"),   # rounding slider shown — the tallest of the three
    ("svg", "square"),    # SVG reasons shown, size hint blank
)

SIZES = ("small", "medium", "large")
DEFAULT_SIZE = "medium"

PREVIEW_SIZE = (360, 360)
LOGO_CHIP_SIZE = (32, 32)
# The preview always renders at this module size regardless of the chosen output
# size: it is only ever shown at PREVIEW_SIZE, and rendering a Large code just to
# shrink it wastes real time on the logo path, where every candidate placement is
# decode-checked at full resolution.
PREVIEW_BOX_SIZE = 10
# Long enough to coalesce typing, short enough to feel immediate. A plain render
# takes ~4ms and a logo render ~190ms, so no spinner is warranted.
DEBOUNCE_MS = 300
POLL_MS = 50

# Tk renders missing glyphs as empty boxes rather than falling back, so a
# language whose script the default UI font does not cover needs a font chosen
# for it. Listed best-first per platform; the first installed one wins, and if
# none is present we keep the default rather than failing.
CJK_FONT_CANDIDATES = {
    "darwin": ("PingFang TC", "Heiti TC", "Apple LiGothic", "Arial Unicode MS"),
    "win32": ("Microsoft JhengHei UI", "Microsoft JhengHei", "MingLiU", "SimSun"),
    "other": (
        "Noto Sans CJK TC",
        "Noto Sans CJK SC",
        "Noto Sans TC",
        "WenQuanYi Zen Hei",
        "AR PL UMing TW",
        "Droid Sans Fallback",
    ),
}
# Languages whose script needs the fallback above, by language-code prefix.
CJK_LANGUAGE_PREFIXES = ("zh", "ja", "ko")
# The Tk named fonts every widget class derives from.
NAMED_FONTS = ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont")

NEUTRAL, WORKING, SUCCESS, PROBLEM = "neutral", "working", "success", "problem"
BANNER_ICONS = {NEUTRAL: "", WORKING: "", SUCCESS: "✓", PROBLEM: "⚠"}
BANNER_COLOURS = {NEUTRAL: "#5f6368", WORKING: "#1a73e8", SUCCESS: "#1e8e3e", PROBLEM: "#d93025"}

# Engine failure codes mapped onto our own copy, so the GUI never matches on
# English message text.
ERROR_IDS = {
    "url_required": "error.no_url",
    "image_unreadable": "error.bad_image",
    "image_not_found": "error.image_missing",
    "overlay_no_fit": "error.logo_too_big",
    "folder_missing": "error.folder_missing",
    "save_failed": "error.save_failed",
    "opencv_missing": "error.opencv_missing",
}
# Engine notices worth putting in the banner. The SVG warnings are deliberately
# absent: the disclosure lines beside the disabled controls already say why, and
# repeating it in the banner reads as an error when nothing is wrong.
NOTICE_IDS = {
    "image_downscaled": "notice.image_downscaled",
}


def normalise_url(raw: str) -> str:
    """Add https:// when the text is clearly a bare domain. Never rejects input."""
    text = raw.strip()
    if not text or "://" in text:
        return text
    head = text.split("/", 1)[0]
    if " " not in text and "." in head and not head.endswith("."):
        return f"https://{text}"
    return text


def default_filename(url: str, output_format: str) -> str:
    """A ready-made name so the save dialog is never blank. Stays ASCII on purpose."""
    host = urlparse(url).netloc or urlparse(url).path
    slug = re.sub(r"[^a-z0-9]+", "-", host.lower()).strip("-")
    return f"qr-{slug or 'code'}{EXTENSIONS[output_format]}"


def friendly_path(path: Path) -> str:
    try:
        return f"~/{path.relative_to(Path.home())}"
    except ValueError:
        return str(path)


class QRGeneratorApp(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=16)
        self.master = master
        self.grid(sticky="nsew")

        self.tr = Translator(load_language())

        self.url_var = tk.StringVar()
        self.format_var = tk.StringVar(value="png")
        self.style_var = tk.StringVar(value=DEFAULT_STYLE)
        self.softness_var = tk.DoubleVar(value=DEFAULT_SOFTNESS)
        self.size_var = tk.StringVar(value=DEFAULT_SIZE)
        self.overlay_path_var = tk.StringVar()
        self.language_var = tk.StringVar(value=self.tr.language)
        self.language_display_var = tk.StringVar(value=LANGUAGES[self.tr.language])

        # Render state. A job token replaces the old preview-signature gate:
        # results whose token is stale are dropped, so the preview is always
        # either current or on its way, and Save never depends on it.
        self._queue: queue.Queue[tuple[str, int | None, object]] = queue.Queue()
        self._job_id = 0
        self._pending_render: str | None = None
        self._preview_photo: ImageTk.PhotoImage | None = None
        self._logo_photo: ImageTk.PhotoImage | None = None
        self._last_preview: Image.Image | None = None
        self._saved_path: Path | None = None
        self._save_dir: str | None = None
        self._saving = False
        self._render_thread: threading.Thread | None = None
        self._save_thread: threading.Thread | None = None
        self._rerender_queued = False
        self._measuring = False

        # Deferred display state, re-rendered whenever the language changes.
        self._banner: tuple[str, list[tuple[str, dict]]] = (NEUTRAL, [("status.empty", {})])
        self._readout: tuple[str, dict] | None = None
        self._badge: str | None = None
        self._preview_note: str | None = "preview.placeholder"

        self._init_styles()
        self._apply_font_for_language()  # the saved language may not be Latin-script
        self._build_menu()
        self._build_layout()
        self._register_observers()  # also performs the first render of each
        self._bind_events()
        self._clear_preview()
        self._set_minimum_size()
        self.after(POLL_MS, self._process_queue)

        if os.environ.get("QR_GUI_SMOKE_TEST") == "1":
            self.after(500, self.master.destroy)

    # ------------------------------------------------------------------ setup

    def _init_styles(self) -> None:
        base = tkfont.nametofont("TkDefaultFont")
        size = base.cget("size")
        smaller = size - 1 if size > 0 else size + 1

        self._heading_font = base.copy()
        self._heading_font.configure(weight="bold")
        self._hint_font = base.copy()
        self._hint_font.configure(size=smaller)
        # Remembered so switching back to a Latin-script language restores the
        # platform's own UI font rather than leaving a CJK face behind.
        self._default_families = {
            name: tkfont.nametofont(name).cget("family") for name in self._available_named_fonts()
        }

        style = ttk.Style()
        style.configure("Heading.TLabel", font=self._heading_font)
        style.configure("Hint.TLabel", font=self._hint_font, foreground="#5f6368")
        style.configure("Banner.TLabel", font=base)
        style.configure("Readout.TLabel", font=self._hint_font, foreground="#5f6368")

    def _available_named_fonts(self) -> tuple[str, ...]:
        """Not every Tk build defines every named font."""
        defined = set(self.tk.splitlist(self.tk.call("font", "names")))
        return tuple(name for name in NAMED_FONTS if name in defined)

    def font_family_for_language(self, language: str) -> str | None:
        """The family to use for `language`, or None to keep the platform default."""
        if not language.startswith(CJK_LANGUAGE_PREFIXES):
            return None
        installed = set(tkfont.families(self))
        for candidate in CJK_FONT_CANDIDATES.get(self._platform_key(), ()):
            if candidate in installed:
                return candidate
        return None  # nothing suitable installed; the default is the best we have

    def _apply_font_for_language(self) -> None:
        chosen = self.font_family_for_language(self.tr.language)
        for name in self._available_named_fonts():
            family = chosen or self._default_families.get(name)
            if family:
                tkfont.nametofont(name).configure(family=family)
        for font in (self._heading_font, self._hint_font):
            family = chosen or self._default_families.get("TkDefaultFont")
            if family:
                font.configure(family=family)

    def _build_menu(self) -> None:
        modifier = "Cmd" if sys.platform == "darwin" else "Ctrl"
        menubar = tk.Menu(self.master)
        # Cascades are found by their menu widget rather than by an index
        # recorded at build time: macOS adds its own application menu to the
        # menu bar, which shifts every index after it.
        self._cascade_menus: list[tuple[tk.Menu, str]] = []

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(command=self.start_save, accelerator=f"{modifier}+S")
        file_menu.add_command(command=self.reset_defaults, accelerator=f"{modifier}+R")
        file_menu.add_separator()
        file_menu.add_command(command=self.master.destroy)
        menubar.add_cascade(menu=file_menu, label=self.tr.t("menu.file"))
        self._cascade_menus.append((file_menu, "menu.file"))

        language_menu = tk.Menu(menubar, tearoff=0)
        for code, name in LANGUAGES.items():
            language_menu.add_radiobutton(
                label=name,
                value=code,
                variable=self.language_var,
                command=lambda c=code: self.set_language(c),
            )
        menubar.add_cascade(menu=language_menu, label=self.tr.t("menu.language"))
        self._cascade_menus.append((language_menu, "menu.language"))

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(command=self._show_about)
        menubar.add_cascade(menu=help_menu, label=self.tr.t("menu.help"))
        self._cascade_menus.append((help_menu, "menu.help"))

        self.master.configure(menu=menubar)
        self._menubar = menubar
        self._file_menu = file_menu
        self._help_menu = help_menu

    def _build_layout(self) -> None:
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=3, uniform="cols")
        self.columnconfigure(1, weight=2, uniform="cols")
        self.rowconfigure(1, weight=1)

        self._build_header()
        self._build_form()
        self._build_preview()
        self._build_action_bar()

    def _build_header(self) -> None:
        """The address heading on the left, the language picker on the right.

        The picker lives in the window, not only in the menu bar: on macOS the
        menu bar sits at the top of the screen rather than in the window, so a
        menu-only switcher is effectively undiscoverable. A combobox here behaves
        the same on macOS, Windows and Linux.

        The heading shares this row rather than starting the form below it. The
        picker sets the row height whatever else is in it, so a heading on its own
        row underneath was pure vertical cost. Column 0 spans the form, so the
        heading still lines up with the entry it labels.
        """
        header = ttk.Frame(self)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        header.columnconfigure(0, weight=1)

        self.tr.bind(ttk.Label(header, style="Heading.TLabel"), "text", "field.url.label").grid(
            row=0, column=0, sticky="w"
        )
        self.tr.bind(ttk.Label(header, style="Hint.TLabel"), "text", "menu.language").grid(
            row=0, column=1, sticky="e", padx=(0, 8)
        )
        self.language_combo = ttk.Combobox(
            header,
            textvariable=self.language_display_var,
            # Each language is listed in its own script, the usual convention:
            # someone who only reads Chinese still has to recognise their entry.
            values=tuple(LANGUAGES.values()),
            state="readonly",
            width=14,
        )
        self.language_combo.grid(row=0, column=2, sticky="e")
        self.language_combo.bind("<<ComboboxSelected>>", self._on_language_selected)

    def _build_form(self) -> None:
        form = ttk.Frame(self)
        form.grid(row=1, column=0, sticky="nsew", padx=(0, 16))
        form.columnconfigure(0, weight=1)
        row = 0

        # Web address. Its heading sits in the header row, beside the language
        # picker, so the form starts at the entry — see _build_header.
        self.url_entry = ttk.Entry(form, textvariable=self.url_var)
        self.url_entry.grid(row=row, column=0, sticky="ew", pady=(0, 2))
        row += 1
        self.url_hint = ttk.Label(form, style="Hint.TLabel")
        self.url_hint.grid(row=row, column=0, sticky="w")
        row += 1

        # Look
        self.tr.bind(ttk.Label(form, style="Heading.TLabel"), "text", "section.look").grid(
            row=row, column=0, sticky="w", pady=(16, 4)
        )
        row += 1
        styles_row = ttk.Frame(form)
        styles_row.grid(row=row, column=0, sticky="ew")
        self.style_buttons = []
        for column, name in enumerate(STYLES):
            button = ttk.Radiobutton(styles_row, value=name, variable=self.style_var)
            self.tr.bind(button, "text", f"style.{name}")
            button.grid(row=0, column=column, sticky="w", padx=(0, 10))
            self.style_buttons.append(button)
        row += 1
        self.style_reason = ttk.Label(form, style="Hint.TLabel")
        self.style_reason.grid(row=row, column=0, sticky="w", pady=(4, 0))
        row += 1

        # Corner rounding
        self.rounding_frame = ttk.Frame(form)
        self.rounding_frame.grid(row=row, column=0, sticky="ew", pady=(12, 0))
        self.rounding_frame.columnconfigure(1, weight=1)
        self.tr.bind(ttk.Label(self.rounding_frame), "text", "field.rounding.label").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        self.tr.bind(ttk.Label(self.rounding_frame, style="Hint.TLabel"), "text", "field.rounding.min").grid(
            row=1, column=0, sticky="w", padx=(0, 8)
        )
        self.softness_scale = ttk.Scale(
            self.rounding_frame, from_=0.0, to=0.5, variable=self.softness_var, orient="horizontal"
        )
        self.softness_scale.grid(row=1, column=1, sticky="ew")
        self.tr.bind(ttk.Label(self.rounding_frame, style="Hint.TLabel"), "text", "field.rounding.max").grid(
            row=1, column=2, sticky="w", padx=(8, 0)
        )
        self.rounding_reason = ttk.Label(form, style="Hint.TLabel")
        self.rounding_reason.grid(row=row, column=0, sticky="w", pady=(12, 0))
        row += 1

        # Logo
        self.tr.bind(ttk.Label(form, style="Heading.TLabel"), "text", "section.logo").grid(
            row=row, column=0, sticky="w", pady=(16, 4)
        )
        row += 1
        logo_row = ttk.Frame(form)
        logo_row.grid(row=row, column=0, sticky="ew")
        logo_row.columnconfigure(1, weight=1)
        self.logo_thumb = ttk.Label(logo_row)
        self.logo_thumb.grid(row=0, column=0, padx=(0, 8))
        self.logo_name = ttk.Label(logo_row, style="Hint.TLabel")
        self.logo_name.grid(row=0, column=1, sticky="w")
        self.logo_choose_button = ttk.Button(logo_row, command=self._choose_overlay)
        self.tr.bind(self.logo_choose_button, "text", "logo.choose")
        self.logo_choose_button.grid(row=0, column=2, padx=(8, 6))
        self.logo_remove_button = ttk.Button(logo_row, command=self._clear_overlay)
        self.tr.bind(self.logo_remove_button, "text", "logo.remove")
        self.logo_remove_button.grid(row=0, column=3)
        row += 1
        self.logo_reason = ttk.Label(form, style="Hint.TLabel")
        self.logo_reason.grid(row=row, column=0, sticky="w", pady=(4, 0))
        row += 1

        # Size
        self.tr.bind(ttk.Label(form, style="Heading.TLabel"), "text", "section.size").grid(
            row=row, column=0, sticky="w", pady=(16, 4)
        )
        row += 1
        size_row = ttk.Frame(form)
        size_row.grid(row=row, column=0, sticky="ew")
        self.size_buttons = []
        for column, name in enumerate(SIZES):
            button = ttk.Radiobutton(size_row, value=name, variable=self.size_var)
            self.tr.bind(button, "text", f"size.{name}")
            button.grid(row=0, column=column, sticky="w", padx=(0, 12))
            self.size_buttons.append(button)
        row += 1
        # Text owned by _apply_disclosure, which blanks it for SVG. Binding it
        # here as well would let the binding overwrite that on a language change.
        self.size_hint = ttk.Label(form, style="Hint.TLabel")
        self.size_hint.grid(row=row, column=0, sticky="w", pady=(4, 0))
        row += 1

        # File format
        self.tr.bind(ttk.Label(form, style="Heading.TLabel"), "text", "section.file").grid(
            row=row, column=0, sticky="w", pady=(16, 4)
        )
        row += 1
        format_row = ttk.Frame(form)
        format_row.grid(row=row, column=0, sticky="ew")
        for column, name in enumerate(ALL_FORMATS):
            button = ttk.Radiobutton(format_row, value=name, variable=self.format_var)
            self.tr.bind(button, "text", f"format.{name}")
            button.grid(row=0, column=column, sticky="w", padx=(0, 12))
        row += 1
        self.format_hint = ttk.Label(form, style="Hint.TLabel")
        self.format_hint.grid(row=row, column=0, sticky="w", pady=(4, 0))
        form.rowconfigure(row + 1, weight=1)

        self._autowrap(
            form,
            self.url_hint,
            self.style_reason,
            self.rounding_reason,
            self.logo_reason,
            self.format_hint,
            self.size_hint,
        )

    def _build_preview(self) -> None:
        preview = ttk.Frame(self)
        preview.grid(row=1, column=1, sticky="nsew")
        # Reserve the preview's full size up front. Without this the window's
        # minimum jumps the moment the first code renders, and it can no longer
        # shrink back to the size it started at.
        preview.columnconfigure(0, weight=1, minsize=PREVIEW_SIZE[0])
        preview.rowconfigure(0, weight=1, minsize=PREVIEW_SIZE[1])

        self.preview_label = ttk.Label(preview, anchor="center", justify="center", style="Hint.TLabel")
        self.preview_label.grid(row=0, column=0, sticky="nsew")
        self.scan_badge = ttk.Label(preview, anchor="center", style="Hint.TLabel")
        self.scan_badge.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.size_readout = ttk.Label(preview, anchor="center", style="Readout.TLabel")
        self.size_readout.grid(row=2, column=0, sticky="ew", pady=(2, 0))
        self._autowrap(preview, self.preview_label, self.scan_badge, self.size_readout)

    def _build_action_bar(self) -> None:
        bar = ttk.Frame(self)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        bar.columnconfigure(0, weight=1)

        self.banner_label = ttk.Label(bar, style="Banner.TLabel", anchor="w")
        self.banner_label.grid(row=0, column=0, sticky="ew", padx=(0, 12))

        self.reveal_button = ttk.Button(bar, command=self._reveal_saved_file)
        self.tr.bind(self.reveal_button, "text", f"button.reveal.{self._platform_key()}")
        self.reveal_button.grid(row=0, column=1, padx=(0, 8))
        self.reveal_button.grid_remove()

        self.reset_button = ttk.Button(bar, command=self.reset_defaults)
        self.tr.bind(self.reset_button, "text", "button.reset")
        self.reset_button.grid(row=0, column=2, padx=(0, 8))

        self.save_button = ttk.Button(bar, command=self.start_save)
        self.tr.bind(self.save_button, "text", "button.save")
        self.save_button.grid(row=0, column=3)

        bar.bind("<Configure>", self._wrap_banner, add="+")

    def _register_observers(self) -> None:
        """Anything whose text depends on live state re-renders on language change.

        Every label written imperatively rather than bound to a string ID must be
        registered here, or it keeps whatever language it was written in.
        """
        self.tr.observe(self._render_banner)
        self.tr.observe(self._render_readout)
        self.tr.observe(self._render_badge)
        self.tr.observe(self._render_url_hint)
        self.tr.observe(self._render_logo_chip)
        self.tr.observe(self._render_format_hint)
        self.tr.observe(self._render_preview_note)
        self.tr.observe(self._apply_disclosure)
        self.tr.observe(self._render_title)

    def _bind_events(self) -> None:
        for var in (self.url_var, self.format_var, self.style_var, self.softness_var, self.size_var):
            var.trace_add("write", self._on_form_change)
        # The logo chip reads a file from disk, so it refreshes only when the
        # chosen logo actually changes.
        self.overlay_path_var.trace_add("write", self._on_overlay_change)

        self.master.bind("<Return>", lambda _event: self.start_save())
        self.master.bind("<Control-s>", lambda _event: self.start_save())
        self.master.bind("<Command-s>", lambda _event: self.start_save())
        self.master.bind("<Control-r>", lambda _event: self.reset_defaults())
        self.master.bind("<Command-r>", lambda _event: self.reset_defaults())
        self.master.bind("<Escape>", lambda _event: self.focus_set())

    def _set_minimum_size(self) -> None:
        """Derive the minimum from the tallest layout the user can reach.

        Measuring whatever happens to be on screen is not enough. The rounding
        slider is taller than the one-line reason it replaces, so a minimum taken
        in the default square state left the form ~27px short the moment a
        rounded style was picked — enough to clip the last hint in Chinese, where
        the line height is larger. English had just enough slack to hide it.
        """
        style, output_format = self.style_var.get(), self.format_var.get()
        self._measuring = True
        try:
            width = height = 0
            for probe_format, probe_style in DISCLOSURE_LAYOUTS:
                self.format_var.set(probe_format)
                self.style_var.set(probe_style)
                self._apply_disclosure()
                self._render_format_hint()
                self.master.update_idletasks()
                width = max(width, self.master.winfo_reqwidth())
                height = max(height, self.master.winfo_reqheight())
            self.format_var.set(output_format)
            self.style_var.set(style)
            self._apply_disclosure()
            self._render_format_hint()
        finally:
            self._measuring = False
        self.master.update_idletasks()
        self.master.minsize(width, height)

    def _autowrap(self, container: tk.Misc, *labels: ttk.Label, reserve: int = 8) -> None:
        """Wrap text to the container's width instead of a fixed pixel guess.

        Driven by the *container*, never by the labels themselves: a label's
        wraplength determines its requested width, so measuring the label would
        feed its own output back into the layout and oscillate forever.
        """
        container.bind(
            "<Configure>",
            lambda event: self._wrap_to(event.width - reserve, *labels),
            add="+",
        )

    @staticmethod
    def _wrap_to(width: int, *labels: ttk.Label) -> None:
        target = max(80, width)
        for label in labels:
            # The threshold absorbs the one-pixel jitter of a resize drag.
            if abs(int(label.cget("wraplength") or 0) - target) > 8:
                label.configure(wraplength=target)

    def _wrap_banner(self, event: tk.Event) -> None:
        """The banner shares its row with the buttons, so it gets what they leave."""
        buttons = (self.reveal_button, self.reset_button, self.save_button)
        used = sum(button.winfo_reqwidth() + 8 for button in buttons if button.winfo_manager())
        self._wrap_to(event.width - used - 12, self.banner_label)

    @staticmethod
    def _platform_key() -> str:
        return sys.platform if sys.platform in ("darwin", "win32") else "other"

    # -------------------------------------------------------------- rendering

    def _render_title(self) -> None:
        self.master.title(self.tr.t("app.title"))
        self._file_menu.entryconfigure(0, label=self.tr.t("menu.file.save"))
        self._file_menu.entryconfigure(1, label=self.tr.t("menu.file.reset"))
        self._file_menu.entryconfigure(3, label=self.tr.t("menu.file.quit"))
        self._help_menu.entryconfigure(0, label=self.tr.t("menu.help.about"))
        for menu, string_id in self._cascade_menus:
            index = self._cascade_index(menu)
            if index is not None:
                self._menubar.entryconfigure(index, label=self.tr.t(string_id))

    def _cascade_index(self, menu: tk.Menu) -> int | None:
        last = self._menubar.index("end")
        if last is None:
            return None
        for index in range(last + 1):
            if self._menubar.type(index) != "cascade":
                continue
            if self._menubar.entrycget(index, "menu") == str(menu):
                return index
        return None

    def _render_banner(self) -> None:
        state, parts = self._banner
        icon = BANNER_ICONS[state]
        text = " ".join(self.tr.t(string_id, **params) for string_id, params in parts)
        self.banner_label.configure(
            text=f"{icon} {text}".strip(), foreground=BANNER_COLOURS[state]
        )

    def _render_readout(self) -> None:
        if self._readout is None:
            self.size_readout.configure(text="")
            return
        string_id, params = self._readout
        self.size_readout.configure(text=self.tr.t(string_id, **params))

    def _render_badge(self) -> None:
        if self._badge is None:
            self.scan_badge.configure(text="")
            return
        icon = "✓" if self._badge == "status.scan_ok" else "⚠"
        colour = BANNER_COLOURS[SUCCESS if self._badge == "status.scan_ok" else PROBLEM]
        self.scan_badge.configure(text=f"{icon} {self.tr.t(self._badge)}", foreground=colour)

    def _render_url_hint(self) -> None:
        """Explains the field while it is empty, then reports any scheme we added.

        The label is the only thing telling a first-time user that this address is
        where a *scanner* ends up, not where the file gets saved, so it earns the
        row whenever there is nothing more specific to say.
        """
        raw = self.url_var.get()
        if not raw.strip():
            self.url_hint.configure(text=self.tr.t("field.url.hint_empty"))
            return
        normalised = normalise_url(raw)
        if normalised and normalised != raw.strip():
            self.url_hint.configure(
                text=self.tr.t("field.url.hint_scheme", url=self._elide(normalised))
            )
        else:
            self.url_hint.configure(text="")

    def _elide(self, url: str, limit: int = 48) -> str:
        """Keep a URL echo on one line, cutting the middle rather than the end.

        The window minimum is fixed, so a hint that wraps to a second line pushes
        the bottom of the form out of view — a long enough address could hide the
        file-type hint entirely. The start and end of a URL are the parts worth
        showing: the start carries the scheme this hint exists to confirm, the end
        carries the page.
        """
        if len(url) <= limit:
            return url
        keep = (limit - 1) // 2
        return f"{url[:keep]}…{url[-keep:]}"

    def _render_logo_chip(self) -> None:
        path = self.overlay_path_var.get().strip()
        if not path:
            self._logo_photo = None
            self.logo_thumb.configure(image="")
            self.logo_name.configure(text=self.tr.t("logo.none"))
            return
        self.logo_name.configure(text=Path(path).name)
        try:
            with Image.open(path) as image:
                thumb = image.convert("RGBA")
                thumb.thumbnail(LOGO_CHIP_SIZE, Image.Resampling.LANCZOS)
                self._logo_photo = ImageTk.PhotoImage(thumb)
            self.logo_thumb.configure(image=self._logo_photo)
        except Exception:
            self._logo_photo = None
            self.logo_thumb.configure(image="")

    def _render_format_hint(self) -> None:
        self.format_hint.configure(text=self.tr.t(f"format.{self.format_var.get()}.hint"))

    def _render_preview_note(self) -> None:
        if self._preview_note is None:
            return  # an image is showing
        self.preview_label.configure(image="", text=self.tr.t(self._preview_note))

    def _set_banner(self, state: str, string_id: str, **params: object) -> None:
        self._set_banner_parts(state, [(string_id, params)])

    def _set_banner_parts(self, state: str, parts: list[tuple[str, dict]]) -> None:
        self._banner = (state, parts)
        self._render_banner()

    # ------------------------------------------------------------ interaction

    def set_language(self, language: str) -> None:
        self.tr.set_language(language)
        # Keep both switchers in step: either one can be the origin of a change.
        self.language_var.set(self.tr.language)
        self.language_display_var.set(LANGUAGES[self.tr.language])
        self._apply_font_for_language()
        save_language(self.tr.language)
        self._set_minimum_size()

    def _on_language_selected(self, _event: tk.Event | None = None) -> None:
        chosen = self.language_display_var.get()
        for code, name in LANGUAGES.items():
            if name == chosen:
                self.set_language(code)
                return

    def _show_about(self) -> None:
        messagebox.showinfo(self.tr.t("dialog.about.title"), self.tr.t("dialog.about.body"))

    def _on_form_change(self, *_args: object) -> None:
        # _set_minimum_size drives the format and style vars through every
        # layout to measure them. Those writes are not the user's.
        if self._measuring:
            return
        self._apply_disclosure()
        self._render_url_hint()
        self._render_format_hint()
        self._hide_saved_state()
        self.schedule_render()

    def _on_overlay_change(self, *_args: object) -> None:
        self._render_logo_chip()
        self._on_form_change()

    def _apply_disclosure(self) -> None:
        """Show controls only where they apply, and always say why when they don't."""
        is_svg = self.format_var.get() == "svg"
        style = self.style_var.get()

        for button in self.style_buttons:
            button.state(["disabled"] if is_svg else ["!disabled"])
        self._set_reason(self.style_reason, "field.rounding.na_svg" if is_svg else None)

        # Three states, not two: show the slider, show a reason, or show nothing.
        # For SVG the Look section above already says "SVG files are always
        # square", so repeating it here just prints the same sentence twice.
        show_rounding = not is_svg and style in SOFTNESS_STYLES
        rounding_reason = None if (is_svg or show_rounding) else "field.rounding.na_square"

        if show_rounding:
            self.rounding_frame.grid()
        else:
            self.rounding_frame.grid_remove()
        self._set_reason(self.rounding_reason, rounding_reason)

        # Both logo buttons are owned here, not in _render_logo_chip, because
        # Remove depends on two things at once — whether a logo is set and
        # whether the format can carry one. Split across two functions, whichever
        # ran last would win, and a language change re-runs both.
        has_logo = bool(self.overlay_path_var.get().strip())
        self.logo_choose_button.state(["disabled"] if is_svg else ["!disabled"])
        self.logo_remove_button.state(
            ["disabled"] if is_svg or not has_logo else ["!disabled"]
        )
        self._set_reason(self.logo_reason, "logo.na_svg" if is_svg else None)

        for button in self.size_buttons:
            button.state(["disabled"] if is_svg else ["!disabled"])
        self.size_hint.configure(text="" if is_svg else self.tr.t("size.large_hint"))

    def _set_reason(self, label: ttk.Label, string_id: str | None) -> None:
        if string_id is None:
            label.grid_remove()
        else:
            label.configure(text=self.tr.t(string_id))
            label.grid()

    def _choose_overlay(self) -> None:
        path = filedialog.askopenfilename(
            title=self.tr.t("dialog.logo.title"),
            filetypes=(
                (self.tr.t("filetype.images"), "*.png *.jpg *.jpeg *.ppm *.bmp *.gif *.webp"),
                (self.tr.t("filetype.all"), "*.*"),
            ),
        )
        if path:
            self.overlay_path_var.set(path)

    def _clear_overlay(self) -> None:
        self.overlay_path_var.set("")

    def reset_defaults(self) -> None:
        """Reset the styling but keep what the user typed — retyping a URL is the annoying part."""
        self.format_var.set("png")
        self.style_var.set(DEFAULT_STYLE)
        self.softness_var.set(DEFAULT_SOFTNESS)
        self.size_var.set(DEFAULT_SIZE)
        self.overlay_path_var.set("")
        self.url_entry.focus_set()

    def _hide_saved_state(self) -> None:
        if self._saved_path is not None:
            self._saved_path = None
            self.reveal_button.grid_remove()

    def _reveal_saved_file(self) -> None:
        if self._saved_path is None:
            return
        path = str(self._saved_path)
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", "-R", path], check=False)
            elif sys.platform == "win32":
                subprocess.run(["explorer", f"/select,{path}"], check=False)
            else:
                subprocess.run(["xdg-open", str(self._saved_path.parent)], check=False)
        except OSError:
            pass

    # ----------------------------------------------------------- render cycle

    def schedule_render(self) -> None:
        """Coalesce edits into a single render shortly after typing stops."""
        if self._pending_render is not None:
            self.after_cancel(self._pending_render)
            self._pending_render = None

        if not self.url_var.get().strip():
            self._job_id += 1  # abandon anything in flight
            self._clear_preview()
            self._set_banner(NEUTRAL, "status.empty")
            return

        self._pending_render = self.after(DEBOUNCE_MS, self._start_render)

    def _start_render(self) -> None:
        self._pending_render = None
        if self._render_is_running():
            # One render at a time. A slow one (long URL plus a logo) must not
            # let a queue of workers pile up behind it.
            self._rerender_queued = True
            return

        self._job_id += 1
        job_id = self._job_id

        request = self._build_request(output_path=None, for_preview=True)
        has_logo = bool(request.overlay_path) and request.output_format != "svg"
        self._set_banner(WORKING, "status.rendering_logo" if has_logo else "status.rendering")
        if has_logo:
            self._dim_preview()

        self._render_thread = threading.Thread(
            target=self._render_worker, args=(job_id, request), daemon=True
        )
        self._render_thread.start()

    def _render_worker(self, job_id: int, request: QRRequest) -> None:
        try:
            result = render_qr_preview(request)
        except QRGenerationError as exc:
            self._queue.put(("render_error", job_id, exc))
            return

        scans: bool | None = None
        if result.preview_image is not None:
            try:
                scans = can_decode_to_url(result.preview_image, request.url)
            except Exception:
                scans = None  # no badge rather than a wrong one
        self._queue.put(("render_ok", job_id, (result, scans)))

    def start_save(self) -> None:
        if self._saving:
            return

        url = normalise_url(self.url_var.get())
        if not url:
            self._set_banner(PROBLEM, "error.no_url")
            self.url_entry.focus_set()
            return

        output_format = self.format_var.get()
        chosen = filedialog.asksaveasfilename(
            title=self.tr.t("dialog.save.title"),
            initialfile=default_filename(url, output_format),
            initialdir=self._save_dir or str(Path.home()),
            defaultextension=EXTENSIONS[output_format],
            filetypes=(
                (self.tr.t(f"format.{output_format}"), f"*{EXTENSIONS[output_format]}"),
                (self.tr.t("filetype.all"), "*.*"),
            ),
        )
        if not chosen:
            self._set_banner(NEUTRAL, "status.save_cancelled")
            return

        # The chosen format wins over whatever extension was typed, rather than
        # the filename silently deciding what gets written.
        path = Path(chosen)
        corrected = path.suffix.lower() not in ACCEPTED_EXTENSIONS[output_format]
        if corrected:
            path = path.with_suffix(EXTENSIONS[output_format])

        self._save_dir = str(path.parent)
        self._saving = True
        self._set_banner(WORKING, "status.saving")
        request = self._build_request(output_path=path)
        self._save_thread = threading.Thread(
            target=self._save_worker, args=(request, corrected), daemon=True
        )
        self._save_thread.start()

    def _save_worker(self, request: QRRequest, corrected: bool) -> None:
        try:
            result = generate_qr_file(request)
        except QRGenerationError as exc:
            self._queue.put(("save_error", None, exc))
            return
        self._queue.put(("save_ok", None, (result, corrected)))

    def _process_queue(self) -> None:
        try:
            while True:
                kind, job_id, payload = self._queue.get_nowait()
                if job_id is not None and job_id != self._job_id:
                    continue  # a newer edit has already superseded this render
                if kind == "render_ok":
                    self._apply_render(*payload)
                elif kind == "render_error":
                    self._apply_error(payload)
                elif kind == "save_ok":
                    self._saving = False
                    self._apply_save(*payload)
                elif kind == "save_error":
                    self._saving = False
                    self._apply_error(payload)
        except queue.Empty:
            pass

        if self._rerender_queued and not self._render_is_running():
            self._rerender_queued = False
            self._start_render()

        self.after(POLL_MS, self._process_queue)

    def _render_is_running(self) -> bool:
        return self._render_thread is not None and self._render_thread.is_alive()

    def _apply_render(self, result: QRGenerationResult, scans: bool | None) -> None:
        notices = self._notice_ids(result)

        if result.output_format == "svg":
            self._clear_preview("preview.svg")
            self._readout = ("size.readout_svg", {})
            self._badge = None
        else:
            self._last_preview = result.preview_image
            self._paint(result.preview_image)
            width, height = self._output_pixel_size(result.pixel_size)
            self._readout = (
                "size.readout",
                {"format": StringId(f"format.{result.output_format}"), "w": width, "h": height},
            )
            self._badge = "status.scan_ok" if scans else "status.scan_warn" if scans is False else None
        self._render_readout()
        self._render_badge()

        if notices:
            self._set_banner_parts(NEUTRAL, notices)
        else:
            self._set_banner(NEUTRAL, "status.ready")

    def _apply_save(self, result: QRGenerationResult, corrected: bool) -> None:
        self._saved_path = Path(result.output_path)
        self.reveal_button.grid()
        parts = [("status.saved", {"path": friendly_path(self._saved_path)})]
        if corrected:
            parts.append(
                ("notice.format_corrected", {"format": StringId(f"format.{result.output_format}")})
            )
        self._set_banner_parts(SUCCESS, parts)

    def _apply_error(self, exc: QRGenerationError) -> None:
        string_id = ERROR_IDS.get(getattr(exc, "code", ""), "error.generic")
        params = dict(getattr(exc, "params", {}))
        params.setdefault("reason", str(exc))
        self._set_banner(PROBLEM, string_id, **params)

    @staticmethod
    def _notice_ids(result: QRGenerationResult) -> list[tuple[str, dict]]:
        found = []
        for message in result.messages:
            code = getattr(message, "code", None)
            if code in NOTICE_IDS:
                found.append((NOTICE_IDS[code], dict(getattr(message, "params", {}))))
        return found

    # -------------------------------------------------------------- preview io

    def _paint(self, image: Image.Image | None) -> None:
        if image is None:
            return
        shown = image.copy()
        shown.thumbnail(PREVIEW_SIZE, Image.Resampling.LANCZOS)
        self._preview_photo = ImageTk.PhotoImage(shown)
        self._preview_note = None  # an image is showing, so there is no text
        self.preview_label.configure(image=self._preview_photo, text="")

    def _dim_preview(self) -> None:
        """Keep the last good code on screen while the next one renders."""
        if self._last_preview is None:
            return
        faded = self._last_preview.convert("RGB")
        self._paint(Image.blend(faded, Image.new("RGB", faded.size, "white"), 0.55))

    def _clear_preview(self, note_id: str = "preview.placeholder") -> None:
        self._preview_photo = None
        self._last_preview = None
        self._readout = None
        self._badge = None
        self._preview_note = note_id
        self._render_preview_note()
        self._render_readout()
        self._render_badge()

    def _build_request(self, *, output_path: Path | None, for_preview: bool = False) -> QRRequest:
        return QRRequest(
            url=normalise_url(self.url_var.get()),
            output_path=output_path,
            output_format=self.format_var.get(),
            overlay_path=self.overlay_path_var.get().strip() or None,
            style=self.style_var.get(),
            softness=round(float(self.softness_var.get()), 3),
            overlay_scope="any",
            box_size=PREVIEW_BOX_SIZE if for_preview else BOX_SIZE_PRESETS[self.size_var.get()],
        )

    def _output_pixel_size(self, preview_size: tuple[int, int] | None) -> tuple[int, int]:
        """Scale a preview's dimensions up to what saving would actually produce.

        Exact rather than approximate: a rendered code is always
        (modules + 2 * border) * box_size pixels on each side.
        """
        if not preview_size:
            return (0, 0)
        scale = BOX_SIZE_PRESETS[self.size_var.get()] / PREVIEW_BOX_SIZE
        return (int(preview_size[0] * scale), int(preview_size[1] * scale))

    def destroy(self) -> None:
        self.tr.clear()
        super().destroy()


def create_app() -> tuple[tk.Tk, QRGeneratorApp]:
    root = tk.Tk()
    app = QRGeneratorApp(root)
    return root, app


def main() -> None:
    root, app = create_app()
    app.url_entry.focus_set()
    root.mainloop()


if __name__ == "__main__":
    main()
