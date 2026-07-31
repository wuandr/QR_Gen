from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import qrcode
import qrcode.image.svg
from PIL import Image, ImageDraw


SUPPORTED_FORMATS = {"png", "jpeg", "jpg", "svg"}
SUPPORTED_STYLES = {"square", "rounded", "dot", "smooth", "diag_rounded"}
MAX_OVERLAY_IMAGE_SIDE = 1024
DEFAULT_BORDER = 4
DEFAULT_BOX_SIZE = 10
MIN_BOX_SIZE = 1
MAX_BOX_SIZE = 100
# Named sizes shared by the GUI and the CLI. Values are qrcode box sizes in
# pixels per module; a short URL renders at 33 modules, so 10/20/40 give
# roughly 330/660/1320 px squares.
BOX_SIZE_PRESETS = {"small": 10, "medium": 20, "large": 40}
# Pillow encoder names. Passed to Image.save explicitly so the requested format
# wins even when the output filename carries a different extension.
PIL_ENCODERS = {"png": "PNG", "jpg": "JPEG", "jpeg": "JPEG"}
DEFAULT_STYLE = "square"
DEFAULT_SOFTNESS = 0.35
INNER_FILL_RATIO = 1
KNOCKOUT_RATIO_CANDIDATES = (0.38, 0.36, 0.34, 0.32, 0.30, 0.28, 0.26, 0.24, 0.22, 0.20, 0.18)
OVERLAY_BORDER_CANDIDATES = (4, 5, 6, 7, 8)

OverlayScope = Literal["project_root", "any"]


class QRGenerationError(ValueError):
    """Raised when the QR request cannot be completed.

    Carries a stable ``code`` alongside the English message so callers can map
    the failure onto their own copy instead of matching on the message text.
    """

    def __init__(self, message: str, code: str = "unknown", **params: object) -> None:
        super().__init__(message)
        self.code = code
        self.params = params


class Notice(str):
    """An informational engine message that also carries a code and params.

    Subclasses ``str`` so existing consumers (the CLI, logs) keep working while
    the GUI reads ``code``/``params`` to render translated copy.
    """

    code: str
    params: dict[str, object]

    def __new__(cls, code: str, text: str, **params: object) -> "Notice":
        notice = super().__new__(cls, text)
        notice.code = code
        notice.params = params
        return notice


@dataclass(frozen=True)
class QRRequest:
    url: str
    output_path: str | Path | None = None
    overlay_path: str | None = None
    style: str = DEFAULT_STYLE
    softness: float = DEFAULT_SOFTNESS
    overlay_scope: OverlayScope = "project_root"
    output_format: str | None = None
    box_size: int = DEFAULT_BOX_SIZE


@dataclass(frozen=True)
class ValidatedQRRequest:
    url: str
    output_path: Path | None
    output_format: str
    overlay_path: str | None
    style: str
    softness: float
    overlay_scope: OverlayScope
    box_size: int = DEFAULT_BOX_SIZE


@dataclass
class OverlayLoadResult:
    image: Image.Image
    path: Path
    messages: list[str] = field(default_factory=list)


@dataclass
class QRGenerationResult:
    output_path: Path | None
    output_format: str
    messages: list[str] = field(default_factory=list)
    preview_image: Image.Image | None = None
    pixel_size: tuple[int, int] | None = None


def validate_request(request: QRRequest, *, require_output_path: bool = True) -> ValidatedQRRequest:
    url = request.url.strip()
    if not url:
        raise QRGenerationError("URL is required.", code="url_required")

    output_path = Path(request.output_path).expanduser() if request.output_path is not None else None
    if output_path is None and require_output_path:
        raise QRGenerationError("An output path is required.", code="output_path_required")

    if request.output_format is not None:
        output_format = request.output_format.strip().lstrip(".").lower()
    elif output_path is not None:
        output_format = output_path.suffix.lstrip(".").lower()
        if not output_format:
            raise QRGenerationError(
                f"Could not determine format from '{output_path}'. Use an extension like .png, .jpg, or .svg.",
                code="format_unknown",
                path=str(output_path),
            )
    else:
        raise QRGenerationError(
            "An output format is required when no output path is given.", code="format_required"
        )

    if output_format not in SUPPORTED_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_FORMATS))
        raise QRGenerationError(
            f"Unsupported format '{output_format}'. Choose from: {supported}.",
            code="format_unsupported",
            format=output_format,
        )

    if output_path is not None:
        output_dir = output_path.parent
        if not output_dir.exists():
            raise QRGenerationError(
                f"Output directory does not exist: {output_dir}",
                code="folder_missing",
                folder=str(output_dir),
            )

    try:
        box_size = int(request.box_size)
    except (TypeError, ValueError) as exc:
        raise QRGenerationError(
            f"Size must be a whole number between {MIN_BOX_SIZE} and {MAX_BOX_SIZE}.", code="size_invalid"
        ) from exc

    if not (MIN_BOX_SIZE <= box_size <= MAX_BOX_SIZE):
        raise QRGenerationError(
            f"Size must be between {MIN_BOX_SIZE} and {MAX_BOX_SIZE}.", code="size_invalid"
        )

    if request.style not in SUPPORTED_STYLES:
        supported = ", ".join(sorted(SUPPORTED_STYLES))
        raise QRGenerationError(
            f"Unsupported style '{request.style}'. Choose from: {supported}.",
            code="style_unsupported",
            style=request.style,
        )

    try:
        softness = float(request.softness)
    except (TypeError, ValueError) as exc:
        raise QRGenerationError(
            "Softness must be a number between 0.0 and 0.5.", code="softness_invalid"
        ) from exc

    if not (0.0 <= softness <= 0.5):
        raise QRGenerationError("Softness must be between 0.0 and 0.5.", code="softness_invalid")

    if request.overlay_scope not in ("project_root", "any"):
        raise QRGenerationError(
            f"Unsupported overlay scope '{request.overlay_scope}'.", code="overlay_scope_invalid"
        )

    return ValidatedQRRequest(
        url=url,
        output_path=output_path,
        output_format=output_format,
        overlay_path=request.overlay_path,
        style=request.style,
        softness=softness,
        overlay_scope=request.overlay_scope,
        box_size=box_size,
    )


def resolve_overlay_path(
    overlay_path: str,
    *,
    overlay_scope: OverlayScope = "project_root",
    project_root: Path | None = None,
) -> Path:
    raw = Path(overlay_path).expanduser()

    if overlay_scope == "project_root":
        project_root = (project_root or Path.cwd()).resolve()
        if raw.is_absolute():
            raise QRGenerationError(
                "--image must be a filename in the project root, not an absolute path.",
                code="image_scope_invalid",
            )

        candidate = (project_root / raw).resolve()
        if candidate.parent != project_root:
            raise QRGenerationError(
                "--image must point to a file directly in the project root.", code="image_scope_invalid"
            )
    else:
        candidate = raw.resolve()

    if not candidate.is_file():
        raise QRGenerationError(
            f"Image file not found: {candidate}", code="image_not_found", path=str(candidate)
        )

    return candidate


def load_overlay_image(
    overlay_path: str,
    *,
    overlay_scope: OverlayScope = "project_root",
    project_root: Path | None = None,
) -> OverlayLoadResult:
    resolved = resolve_overlay_path(
        overlay_path,
        overlay_scope=overlay_scope,
        project_root=project_root,
    )
    try:
        overlay = Image.open(resolved).convert("RGBA")
    except Exception as exc:
        raise QRGenerationError(
            f"Failed to open image '{resolved.name}': {exc}", code="image_unreadable", name=resolved.name
        ) from exc

    messages: list[str] = []
    width, height = overlay.size
    if width > MAX_OVERLAY_IMAGE_SIDE or height > MAX_OVERLAY_IMAGE_SIDE:
        scale = min(MAX_OVERLAY_IMAGE_SIDE / width, MAX_OVERLAY_IMAGE_SIDE / height)
        new_size = (
            max(1, int(width * scale)),
            max(1, int(height * scale)),
        )
        overlay = overlay.resize(new_size, Image.Resampling.LANCZOS)
        messages.append(
            Notice(
                "image_downscaled",
                f"Info: downscaled image '{resolved.name}' from {width}x{height} to {new_size[0]}x{new_size[1]}.",
                name=resolved.name,
                w=new_size[0],
                h=new_size[1],
            )
        )

    return OverlayLoadResult(image=overlay, path=resolved, messages=messages)


def can_decode_to_url(candidate_img: Image.Image, expected_url: str) -> bool:
    """Validate the rendered QR by decoding it with OpenCV."""
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise QRGenerationError(
            "OpenCV is required for adaptive overlay sizing. Install dependency: opencv-python-headless",
            code="opencv_missing",
        ) from exc

    detector = cv2.QRCodeDetector()
    rgb = candidate_img.convert("RGB")
    arr = np.array(rgb)
    bgr = arr[:, :, ::-1]
    decoded, points, _ = detector.detectAndDecode(bgr)
    return bool(points is not None and decoded == expected_url)


def overlay_image(
    qr_img: Image.Image,
    overlay_img: Image.Image,
    modules_count: int,
    box_size: int,
    border: int,
    knockout_modules: int,
) -> Image.Image:
    """Place a user image over a grid-aligned square knockout at the QR centre."""
    qr_rgba = qr_img.convert("RGBA")
    data_start = border * box_size

    knockout_size = knockout_modules * box_size
    offset_modules = (modules_count - knockout_modules) // 2
    knockout_pos = (
        data_start + offset_modules * box_size,
        data_start + offset_modules * box_size,
    )

    knockout = Image.new("RGBA", (knockout_size, knockout_size), (255, 255, 255, 255))
    qr_rgba.paste(knockout, knockout_pos)

    target_size = max(16, int(knockout_size * INNER_FILL_RATIO))
    src_w, src_h = overlay_img.size
    scale = min(target_size / src_w, target_size / src_h)
    resized = overlay_img.resize(
        (max(1, int(src_w * scale)), max(1, int(src_h * scale))),
        Image.Resampling.LANCZOS,
    )

    pos = (
        knockout_pos[0] + (knockout_size - resized.size[0]) // 2,
        knockout_pos[1] + (knockout_size - resized.size[1]) // 2,
    )
    qr_rgba.paste(resized, pos, mask=resized)
    return qr_rgba


def resolve_knockout_modules(modules_count: int, ratio: float) -> int:
    """Convert a ratio to an odd module count, clamped to a safe central region."""
    knockout_modules = max(5, int(modules_count * ratio))
    if knockout_modules % 2 == 0:
        knockout_modules += 1
    knockout_modules = min(knockout_modules, max(5, modules_count - 8))
    if knockout_modules % 2 == 0:
        knockout_modules -= 1
    return knockout_modules


def place_largest_validated_overlay(
    qr_img: Image.Image,
    overlay_img: Image.Image,
    url: str,
    modules_count: int,
    box_size: int,
    border: int,
) -> Image.Image | None:
    """Try largest-first knockout sizes and keep the biggest one that still scans."""
    tested_modules = set()
    for ratio in KNOCKOUT_RATIO_CANDIDATES:
        knockout_modules = resolve_knockout_modules(modules_count, ratio)
        if knockout_modules in tested_modules:
            continue
        tested_modules.add(knockout_modules)

        candidate = overlay_image(
            qr_img=qr_img,
            overlay_img=overlay_img,
            modules_count=modules_count,
            box_size=box_size,
            border=border,
            knockout_modules=knockout_modules,
        )
        if can_decode_to_url(candidate, url):
            return candidate

    return None


def build_qr(url: str, error_correction: int, border: int, box_size: int = DEFAULT_BOX_SIZE) -> qrcode.QRCode:
    qr = qrcode.QRCode(
        error_correction=error_correction,
        border=border,
        box_size=box_size,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return qr


def is_finder_module(row: int, col: int, modules_count: int) -> bool:
    """Keep finder patterns square for better scanner compatibility."""
    in_top = row < 7
    in_bottom = row >= modules_count - 7
    in_left = col < 7
    in_right = col >= modules_count - 7
    return (in_top and in_left) or (in_top and in_right) or (in_bottom and in_left)


def draw_smooth_module(
    draw: ImageDraw.ImageDraw,
    matrix: list[list[bool]],
    row: int,
    col: int,
    x0: int,
    y0: int,
    size: int,
    radius: int,
    corners: tuple[bool, bool, bool, bool] | None = None,
) -> None:
    """Round only the exposed corners while keeping adjacent modules connected."""
    x1 = x0 + size - 1
    y1 = y0 + size - 1
    draw.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill="black", corners=corners)

    if radius <= 0:
        return

    if row > 0 and matrix[row - 1][col]:
        draw.rectangle((x0, y0, x1, y0 + radius), fill="black")
    if row < len(matrix) - 1 and matrix[row + 1][col]:
        draw.rectangle((x0, y1 - radius, x1, y1), fill="black")
    if col > 0 and matrix[row][col - 1]:
        draw.rectangle((x0, y0, x0 + radius, y1), fill="black")
    if col < len(matrix[row]) - 1 and matrix[row][col + 1]:
        draw.rectangle((x1 - radius, y0, x1, y1), fill="black")


def render_qr_image(qr: qrcode.QRCode, style: str, softness: float) -> Image.Image:
    matrix = qr.modules
    modules_count = qr.modules_count
    total_modules = modules_count + (2 * qr.border)
    pixel_size = total_modules * qr.box_size
    img = Image.new("RGBA", (pixel_size, pixel_size), "white")
    draw = ImageDraw.Draw(img)

    radius = int(qr.box_size * softness)
    radius = max(0, min(radius, qr.box_size // 2))

    for row, row_modules in enumerate(matrix):
        for col, is_dark in enumerate(row_modules):
            if not is_dark:
                continue

            x0 = (col + qr.border) * qr.box_size
            y0 = (row + qr.border) * qr.box_size
            x1 = x0 + qr.box_size - 1
            y1 = y0 + qr.box_size - 1

            module_style = style
            if style != "square" and is_finder_module(row, col, modules_count):
                module_style = "square"

            if module_style == "square":
                draw.rectangle((x0, y0, x1, y1), fill="black")
            elif module_style == "rounded":
                draw.rounded_rectangle((x0, y0, x1, y1), radius=radius, fill="black")
            elif module_style == "diag_rounded":
                draw_smooth_module(
                    draw=draw,
                    matrix=matrix,
                    row=row,
                    col=col,
                    x0=x0,
                    y0=y0,
                    size=qr.box_size,
                    radius=radius,
                    corners=(False, True, False, True),
                )
            elif module_style == "dot":
                diameter = max(2, int(qr.box_size * 0.82))
                inset = (qr.box_size - diameter) // 2
                draw.ellipse(
                    (
                        x0 + inset,
                        y0 + inset,
                        x0 + inset + diameter - 1,
                        y0 + inset + diameter - 1,
                    ),
                    fill="black",
                )
            elif module_style == "smooth":
                draw_smooth_module(
                    draw=draw,
                    matrix=matrix,
                    row=row,
                    col=col,
                    x0=x0,
                    y0=y0,
                    size=qr.box_size,
                    radius=radius,
                )

    return img


def _render_validated_request(
    validated: ValidatedQRRequest,
    *,
    include_preview: bool,
    save_output: bool,
) -> QRGenerationResult:
    messages: list[str] = []

    if validated.output_format == "svg":
        if validated.overlay_path:
            messages.append(
                Notice(
                    "logo_dropped_svg",
                    "Warning: overlay images are not supported for SVG output. Ignoring selected image.",
                )
            )
        if validated.style != DEFAULT_STYLE:
            messages.append(
                Notice(
                    "style_dropped_svg",
                    f"Warning: style {validated.style!r} is only supported for raster output. Generating square SVG.",
                    style=validated.style,
                )
            )
        img = qrcode.make(validated.url, image_factory=qrcode.image.svg.SvgImage)
        if save_output and validated.output_path is not None:
            try:
                img.save(validated.output_path)
            except OSError as exc:
                raise QRGenerationError(
                    f"Failed to save output '{validated.output_path}': {exc}",
                    code="save_failed",
                    reason=str(exc),
                ) from exc
        return QRGenerationResult(
            output_path=validated.output_path,
            output_format=validated.output_format,
            messages=messages,
            preview_image=None,
        )

    overlay_img: Image.Image | None = None
    if validated.overlay_path:
        overlay = load_overlay_image(
            validated.overlay_path,
            overlay_scope=validated.overlay_scope,
        )
        overlay_img = overlay.image
        messages.extend(overlay.messages)

    if overlay_img:
        img = None
        selected_border = None
        for border in OVERLAY_BORDER_CANDIDATES:
            qr = build_qr(
                url=validated.url,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                border=border,
                box_size=validated.box_size,
            )
            candidate_base = render_qr_image(qr=qr, style=validated.style, softness=validated.softness)

            if not can_decode_to_url(candidate_base, validated.url):
                continue

            placed = place_largest_validated_overlay(
                qr_img=candidate_base,
                overlay_img=overlay_img,
                url=validated.url,
                modules_count=qr.modules_count,
                box_size=qr.box_size,
                border=qr.border,
            )
            if placed is not None:
                img = placed
                selected_border = border
                break

        if img is None:
            raise QRGenerationError(
                "No validated overlay size produced a scannable QR. Try a simpler image or shorter URL.",
                code="overlay_no_fit",
            )
        if selected_border != OVERLAY_BORDER_CANDIDATES[0]:
            messages.append(
                Notice(
                    "border_widened",
                    f"Info: used quiet-zone border={selected_border} for decode-stable overlay validation.",
                    border=selected_border,
                )
            )
    else:
        qr = build_qr(
            url=validated.url,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            border=DEFAULT_BORDER,
            box_size=validated.box_size,
        )
        img = render_qr_image(qr=qr, style=validated.style, softness=validated.softness)

    if validated.output_format in ("jpeg", "jpg"):
        img = img.convert("RGB")

    preview_image = img.copy() if include_preview else None

    if save_output and validated.output_path is not None:
        try:
            img.save(validated.output_path, format=PIL_ENCODERS[validated.output_format])
        except OSError as exc:
            raise QRGenerationError(
                f"Failed to save output '{validated.output_path}': {exc}",
                code="save_failed",
                reason=str(exc),
            ) from exc

    return QRGenerationResult(
        output_path=validated.output_path,
        output_format=validated.output_format,
        messages=messages,
        preview_image=preview_image,
        pixel_size=img.size,
    )


def render_qr_preview(request: QRRequest) -> QRGenerationResult:
    validated = validate_request(request, require_output_path=False)
    return _render_validated_request(validated, include_preview=True, save_output=False)


def generate_qr_file(request: QRRequest, *, include_preview: bool = False) -> QRGenerationResult:
    validated = validate_request(request)
    return _render_validated_request(validated, include_preview=include_preview, save_output=True)
