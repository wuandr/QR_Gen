from __future__ import annotations

import os
import queue
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from PIL import Image, ImageTk

from qr_core import (
    DEFAULT_SOFTNESS,
    DEFAULT_STYLE,
    QRGenerationError,
    QRGenerationResult,
    QRRequest,
    SUPPORTED_STYLES,
    generate_qr_file,
    render_qr_preview,
)


RASTER_FORMATS = ("PNG", "JPEG")
ALL_FORMATS = RASTER_FORMATS + ("SVG",)
SOFTNESS_STYLES = {"rounded", "smooth", "diag_rounded"}
PREVIEW_SIZE = (340, 340)


class QRGeneratorApp(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=16)
        self.master = master
        self.grid(sticky="nsew")

        self.url_var = tk.StringVar()
        self.format_var = tk.StringVar(value="PNG")
        self.style_var = tk.StringVar(value=DEFAULT_STYLE)
        self.softness_var = tk.StringVar(value=f"{DEFAULT_SOFTNESS:.2f}")
        self.overlay_path_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Choose options and click Preview.")
        self.preview_note_var = tk.StringVar(value="Raster preview will appear here before you save.")

        self._queue: queue.Queue[tuple[str, str | QRGenerationResult]] = queue.Queue()
        self._preview_photo: ImageTk.PhotoImage | None = None
        self._worker: threading.Thread | None = None
        self._preview_signature: tuple[str, str, str, str, str] | None = None

        self._build_layout()
        self._bind_events()
        self._update_control_states()
        self.after(100, self._process_queue)

        if os.environ.get("QR_GUI_SMOKE_TEST") == "1":
            self.after(500, self.master.destroy)

    def _build_layout(self) -> None:
        self.master.title("QR Generator")
        self.master.minsize(860, 540)
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        form = ttk.Frame(self)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="URL").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.url_entry = ttk.Entry(form, textvariable=self.url_var)
        self.url_entry.grid(row=0, column=1, columnspan=3, sticky="ew", pady=(0, 8))

        ttk.Label(form, text="Format").grid(row=1, column=0, sticky="w", pady=8)
        self.format_combo = ttk.Combobox(form, textvariable=self.format_var, values=ALL_FORMATS, state="readonly")
        self.format_combo.grid(row=1, column=1, sticky="ew", pady=8)

        ttk.Label(form, text="Style").grid(row=1, column=2, sticky="w", padx=(12, 0), pady=8)
        self.style_combo = ttk.Combobox(
            form,
            textvariable=self.style_var,
            values=tuple(sorted(SUPPORTED_STYLES)),
            state="readonly",
        )
        self.style_combo.grid(row=1, column=3, sticky="ew", pady=8)

        ttk.Label(form, text="Softness").grid(row=2, column=0, sticky="w", pady=8)
        self.softness_entry = ttk.Entry(form, textvariable=self.softness_var)
        self.softness_entry.grid(row=2, column=1, sticky="ew", pady=8)
        ttk.Label(form, text="Range: 0.0 to 0.5").grid(row=2, column=2, columnspan=2, sticky="w", padx=(12, 0), pady=8)

        ttk.Label(form, text="Overlay Image").grid(row=3, column=0, sticky="w", pady=8)
        self.overlay_entry = ttk.Entry(form, textvariable=self.overlay_path_var)
        self.overlay_entry.grid(row=3, column=1, sticky="ew", pady=8)
        self.overlay_browse_button = ttk.Button(form, text="Browse", command=self._choose_overlay)
        self.overlay_browse_button.grid(row=3, column=2, sticky="ew", padx=(12, 6), pady=8)
        self.overlay_clear_button = ttk.Button(form, text="Clear", command=self._clear_overlay)
        self.overlay_clear_button.grid(row=3, column=3, sticky="ew", pady=8)

        actions = ttk.Frame(form)
        actions.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(16, 8))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)
        self.preview_button = ttk.Button(actions, text="Preview", command=self.start_preview)
        self.preview_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.save_button = ttk.Button(actions, text="Save", command=self.start_save, state="disabled")
        self.save_button.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.reset_button = ttk.Button(actions, text="Reset", command=self.reset_defaults)
        self.reset_button.grid(row=0, column=2, sticky="ew")

        ttk.Label(form, text="Status").grid(row=5, column=0, sticky="nw", pady=(12, 8))
        self.status_label = ttk.Label(form, textvariable=self.status_var, wraplength=420, justify="left")
        self.status_label.grid(row=5, column=1, columnspan=3, sticky="ew", pady=(12, 8))

        preview = ttk.LabelFrame(self, text="Preview")
        preview.grid(row=0, column=1, sticky="nsew")
        preview.columnconfigure(0, weight=1)
        preview.rowconfigure(0, weight=1)
        preview.rowconfigure(1, weight=0)

        self.preview_label = ttk.Label(preview, anchor="center")
        self.preview_label.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 8))
        self.preview_note = ttk.Label(preview, textvariable=self.preview_note_var, wraplength=300, justify="center")
        self.preview_note.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

    def _bind_events(self) -> None:
        self.url_var.trace_add("write", self._on_form_change)
        self.format_var.trace_add("write", self._on_form_change)
        self.style_var.trace_add("write", self._on_form_change)
        self.softness_var.trace_add("write", self._on_form_change)
        self.overlay_path_var.trace_add("write", self._on_form_change)

    def _on_form_change(self, *_args: object) -> None:
        self._update_control_states()
        self._invalidate_preview_if_needed()

    def _update_control_states(self) -> None:
        output_format = self.format_var.get().upper()
        style = self.style_var.get()

        svg_selected = output_format == "SVG"
        softness_enabled = not svg_selected and style in SOFTNESS_STYLES

        self.style_combo.configure(state="disabled" if svg_selected else "readonly")
        self.softness_entry.configure(state="normal" if softness_enabled else "disabled")
        self.overlay_entry.configure(state="disabled" if svg_selected else "normal")
        self.overlay_browse_button.configure(state="disabled" if svg_selected else "normal")
        clear_state = "disabled" if svg_selected and not self.overlay_path_var.get() else "normal"
        self.overlay_clear_button.configure(state=clear_state)
        if self._is_busy():
            self.save_button.configure(state="disabled")
        elif self._preview_signature and self._preview_signature == self._current_signature():
            self.save_button.configure(state="normal")
        else:
            self.save_button.configure(state="disabled")

    def _choose_overlay(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Overlay Image",
            filetypes=(
                ("Image Files", "*.png *.jpg *.jpeg *.ppm *.bmp *.gif *.webp"),
                ("All Files", "*.*"),
            ),
        )
        if path:
            self.overlay_path_var.set(path)

    def _clear_overlay(self) -> None:
        self.overlay_path_var.set("")
        self._update_control_states()

    def reset_defaults(self) -> None:
        if self._is_busy():
            return
        self.url_var.set("")
        self.format_var.set("PNG")
        self.style_var.set(DEFAULT_STYLE)
        self.softness_var.set(f"{DEFAULT_SOFTNESS:.2f}")
        self.overlay_path_var.set("")
        self.status_var.set("Choose options and click Preview.")
        self._preview_signature = None
        self._clear_preview("Raster preview will appear here before you save.")
        self.url_entry.focus_set()
        self._update_control_states()

    def _validate_form(self) -> tuple[str, float] | None:
        url = self.url_var.get().strip()
        if not url:
            self.status_var.set("Enter a URL before generating a QR code.")
            return None

        try:
            softness = float(self.softness_var.get())
        except ValueError:
            self.status_var.set("Softness must be a number between 0.0 and 0.5.")
            return None

        if not (0.0 <= softness <= 0.5):
            self.status_var.set("Softness must be between 0.0 and 0.5.")
            return None

        return url, softness

    def start_preview(self) -> None:
        if self._is_busy():
            return

        validated = self._validate_form()
        if validated is None:
            return
        url, softness = validated

        request = self._build_request(url=url, softness=softness, output_path=self._preview_output_path())
        self._set_busy(True)
        self.status_var.set("Rendering preview...")
        self._worker = threading.Thread(target=self._preview_worker, args=(request,), daemon=True)
        self._worker.start()

    def start_save(self) -> None:
        if self._is_busy():
            return

        validated = self._validate_form()
        if validated is None:
            return
        if self._preview_signature is None:
            self.status_var.set("Click Preview before saving.")
            return
        if self._preview_signature != self._current_signature():
            self.status_var.set("Preview is out of date. Click Preview again before saving.")
            return

        url, softness = validated
        extension_map = {
            "PNG": ".png",
            "JPEG": ".jpg",
            "SVG": ".svg",
        }
        output_format = self.format_var.get().upper()
        output_path = filedialog.asksaveasfilename(
            title="Save QR Code",
            defaultextension=extension_map[output_format],
            filetypes=(
                (f"{output_format} Files", f"*{extension_map[output_format]}"),
                ("All Files", "*.*"),
            ),
        )
        if not output_path:
            self.status_var.set("Save cancelled.")
            return

        request = self._build_request(url=url, softness=softness, output_path=output_path)
        self._set_busy(True)
        self.status_var.set("Saving QR code...")
        self._worker = threading.Thread(target=self._save_worker, args=(request,), daemon=True)
        self._worker.start()

    def _preview_worker(self, request: QRRequest) -> None:
        try:
            result = render_qr_preview(request)
        except QRGenerationError as exc:
            self._queue.put(("preview_error", str(exc)))
            return
        self._queue.put(("preview_success", result))

    def _save_worker(self, request: QRRequest) -> None:
        try:
            result = generate_qr_file(request, include_preview=False)
        except QRGenerationError as exc:
            self._queue.put(("save_error", str(exc)))
            return
        self._queue.put(("save_success", result))

    def _process_queue(self) -> None:
        try:
            while True:
                status, payload = self._queue.get_nowait()
                if status in {"preview_error", "save_error"}:
                    self._set_busy(False)
                    self.status_var.set(f"Error: {payload}")
                    self._worker = None
                elif status == "preview_success":
                    result = payload
                    self._set_busy(False)
                    self._apply_preview_result(result)
                    self._worker = None
                else:
                    result = payload
                    self._set_busy(False)
                    self._apply_save_result(result)
                    self._worker = None
        except queue.Empty:
            pass
        self.after(100, self._process_queue)

    def _apply_preview_result(self, result: QRGenerationResult) -> None:
        self._preview_signature = self._current_signature()
        message_lines = list(result.messages)
        if result.output_format == "svg":
            message_lines.append("Preview ready. Inline SVG preview is not shown. Click Save to export the file.")
            self._clear_preview("Inline SVG preview is not available. Click Save to export the current SVG.")
        else:
            preview_image = result.preview_image.copy() if result.preview_image is not None else None
            if preview_image is not None:
                preview_image.thumbnail(PREVIEW_SIZE, Image.Resampling.LANCZOS)
                self._preview_photo = ImageTk.PhotoImage(preview_image)
                self.preview_label.configure(image=self._preview_photo, text="")
            self.preview_note_var.set("Preview ready. Review it, then click Save to export.")
            message_lines.append("Preview ready. Click Save to export this QR code.")
        self.status_var.set("\n".join(message_lines))
        self._update_control_states()

    def _apply_save_result(self, result: QRGenerationResult) -> None:
        message_lines = list(result.messages) + [f"Saved QR code to: {result.output_path}"]
        self.status_var.set("\n".join(message_lines))
        if result.output_format == "svg":
            self.preview_note_var.set("Inline SVG preview is not available. Open the saved SVG file to inspect it.")
        else:
            self.preview_note_var.set("Saved from the current preview.")

    def _clear_preview(self, note: str) -> None:
        self._preview_photo = None
        self.preview_label.configure(image="", text="")
        self.preview_note_var.set(note)

    def _set_busy(self, busy: bool) -> None:
        button_state = "disabled" if busy else "normal"
        self.preview_button.configure(state=button_state)
        self.reset_button.configure(state=button_state)
        self.url_entry.configure(state=button_state)
        self.format_combo.configure(state="disabled" if busy else "readonly")
        self.softness_entry.configure(state="disabled" if busy else self.softness_entry.cget("state"))
        self.overlay_entry.configure(state="disabled" if busy else self.overlay_entry.cget("state"))
        self.overlay_browse_button.configure(state=button_state)
        self.overlay_clear_button.configure(state=button_state if busy else "normal")
        self.style_combo.configure(state="disabled" if busy else "readonly")
        if not busy:
            self._update_control_states()
        else:
            self.save_button.configure(state="disabled")

    def _is_busy(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def _current_signature(self) -> tuple[str, str, str, str, str]:
        return (
            self.url_var.get().strip(),
            self.format_var.get().upper(),
            self.style_var.get(),
            self.softness_var.get().strip(),
            self.overlay_path_var.get().strip(),
        )

    def _invalidate_preview_if_needed(self) -> None:
        if self._preview_signature is None:
            return
        if self._preview_signature == self._current_signature():
            return
        self._preview_signature = None
        self._clear_preview("Preview is out of date. Click Preview again to refresh it.")
        if not self._is_busy():
            self.status_var.set("Preview is out of date. Click Preview again before saving.")
        self._update_control_states()

    def _build_request(self, *, url: str, softness: float, output_path: str | os.PathLike[str]) -> QRRequest:
        overlay_path = self.overlay_path_var.get().strip() or None
        return QRRequest(
            url=url,
            output_path=output_path,
            overlay_path=overlay_path,
            style=self.style_var.get(),
            softness=softness,
            overlay_scope="any",
        )

    def _preview_output_path(self) -> str:
        extension_map = {
            "PNG": ".png",
            "JPEG": ".jpg",
            "SVG": ".svg",
        }
        output_format = self.format_var.get().upper()
        preview_name = f"qr_generator_preview{extension_map[output_format]}"
        return str(Path(tempfile.gettempdir()) / preview_name)


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
