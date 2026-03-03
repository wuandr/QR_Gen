import argparse
import os
import sys
from pathlib import Path
import qrcode
import qrcode.image.svg
from PIL import Image, ImageDraw


SUPPORTED_FORMATS = {"png", "jpeg", "jpg", "svg"}
SUPPORTED_STYLES = {"square", "rounded", "dot", "smooth", "diag_rounded"}
MAX_OVERLAY_IMAGE_SIDE = 1024
DEFAULT_BORDER = 4
DEFAULT_BOX_SIZE = 10
DEFAULT_STYLE = "square"
DEFAULT_SOFTNESS = 0.35
INNER_FILL_RATIO = 1
KNOCKOUT_RATIO_CANDIDATES = (0.38, 0.36, 0.34, 0.32, 0.30, 0.28, 0.26, 0.24, 0.22, 0.20, 0.18)
OVERLAY_BORDER_CANDIDATES = (4, 5, 6, 7, 8)


def resolve_overlay_path(overlay_path: str) -> Path:
    """Resolve an overlay image path and keep it scoped to the project root."""
    project_root = Path.cwd().resolve()
    raw = Path(overlay_path)
    if raw.is_absolute():
        print("Error: --image must be a filename in the project root, not an absolute path.")
        sys.exit(1)

    candidate = (project_root / raw).resolve()
    if candidate.parent != project_root:
        print("Error: --image must point to a file directly in the project root.")
        sys.exit(1)
    if not candidate.is_file():
        print(f"Error: image file not found: {candidate.name}")
        sys.exit(1)

    return candidate


def load_overlay_image(overlay_path: str) -> Image.Image:
    """Load and validate the user-provided overlay image."""
    resolved = resolve_overlay_path(overlay_path)
    try:
        overlay = Image.open(resolved).convert("RGBA")
    except Exception as exc:
        print(f"Error: failed to open image '{resolved.name}': {exc}")
        sys.exit(1)

    width, height = overlay.size
    if width > MAX_OVERLAY_IMAGE_SIDE or height > MAX_OVERLAY_IMAGE_SIDE:
        scale = min(MAX_OVERLAY_IMAGE_SIDE / width, MAX_OVERLAY_IMAGE_SIDE / height)
        new_size = (
            max(1, int(width * scale)),
            max(1, int(height * scale)),
        )
        overlay = overlay.resize(new_size, Image.Resampling.LANCZOS)
        print(
            f"Info: downscaled image '{resolved.name}' from {width}x{height} "
            f"to {new_size[0]}x{new_size[1]}."
        )

    return overlay


def resolve_knockout_modules(modules_count: int, ratio: float) -> int:
    """Convert a ratio to an odd module count, clamped to a safe central region."""
    knockout_modules = max(5, int(modules_count * ratio))
    if knockout_modules % 2 == 0:
        knockout_modules += 1
    knockout_modules = min(knockout_modules, max(5, modules_count - 8))
    if knockout_modules % 2 == 0:
        knockout_modules -= 1
    return knockout_modules


def can_decode_to_url(candidate_img: Image.Image, expected_url: str) -> bool:
    """Validate the rendered QR by decoding it with OpenCV."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        print("Error: OpenCV is required for adaptive overlay sizing. Install dependency: opencv-python")
        sys.exit(1)

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

    # White square knockout under the logo improves scan reliability.
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


def build_qr(url: str, error_correction: int, border: int) -> qrcode.QRCode:
    qr = qrcode.QRCode(
        error_correction=error_correction,
        border=border,
        box_size=DEFAULT_BOX_SIZE,
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


def generate_qr(url: str, output: str, image_path: str | None, style: str, softness: float) -> None:
    ext = os.path.splitext(output)[1].lstrip(".").lower()

    if not ext:
        print(f"Error: could not determine format from '{output}'. Use an extension like .png, .jpg, or .svg.")
        sys.exit(1)

    if ext not in SUPPORTED_FORMATS:
        print(f"Error: unsupported format '{ext}'. Choose from: {', '.join(sorted(SUPPORTED_FORMATS))}")
        sys.exit(1)

    overlay_img = load_overlay_image(image_path) if image_path else None

    if ext == "svg":
        if image_path:
            print("Warning: --image is not supported for SVG output. Generating plain SVG.")
        if style != DEFAULT_STYLE:
            print(f"Warning: --style {style!r} is only supported for raster output. Generating square SVG.")
        img = qrcode.make(url, image_factory=qrcode.image.svg.SvgImage)
        img.save(output)
    else:
        if overlay_img:
            img = None
            selected_border = None
            for border in OVERLAY_BORDER_CANDIDATES:
                qr = build_qr(url=url, error_correction=qrcode.constants.ERROR_CORRECT_H, border=border)
                candidate_base = render_qr_image(qr=qr, style=style, softness=softness)

                # Some OpenCV builds are sensitive to quiet-zone width at higher QR versions.
                if not can_decode_to_url(candidate_base, url):
                    continue

                placed = place_largest_validated_overlay(
                    qr_img=candidate_base,
                    overlay_img=overlay_img,
                    url=url,
                    modules_count=qr.modules_count,
                    box_size=qr.box_size,
                    border=qr.border,
                )
                if placed is not None:
                    img = placed
                    selected_border = border
                    break

            if img is None:
                print("Error: no validated overlay size produced a scannable QR. Try a simpler image or shorter URL.")
                sys.exit(1)
            if selected_border != OVERLAY_BORDER_CANDIDATES[0]:
                print(f"Info: used quiet-zone border={selected_border} for decode-stable overlay validation.")
        else:
            qr = build_qr(url=url, error_correction=qrcode.constants.ERROR_CORRECT_M, border=DEFAULT_BORDER)
            img = render_qr_image(qr=qr, style=style, softness=softness)

        if ext in ("jpeg", "jpg"):
            img = img.convert("RGB")

        img.save(output)

    print(f"QR code saved to: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a QR code from a URL.")
    parser.add_argument("url", help="The URL to encode in the QR code")
    parser.add_argument(
        "-o", "--output",
        default="qrcode.png",
        help="Output filename (default: qrcode.png). Format is inferred from the extension.",
    )
    parser.add_argument(
        "--image",
        help=(
            "Overlay image filename in project root (e.g. test_cat_face_1024.ppm). "
            f"Oversized images are downscaled to max {MAX_OVERLAY_IMAGE_SIDE}x{MAX_OVERLAY_IMAGE_SIDE}."
        ),
    )
    parser.add_argument(
        "--style",
        choices=sorted(SUPPORTED_STYLES),
        default=DEFAULT_STYLE,
        help=(
            "Module rendering style for raster outputs: square, rounded, dot, smooth, "
            "or diag_rounded (top-right + bottom-left corners rounded)."
        ),
    )
    parser.add_argument(
        "--softness",
        type=float,
        default=DEFAULT_SOFTNESS,
        help="Corner softness for rounded/smooth/diag_rounded styles in range [0.0, 0.5].",
    )
    args = parser.parse_args()
    if not (0.0 <= args.softness <= 0.5):
        print("Error: --softness must be between 0.0 and 0.5")
        sys.exit(1)
    generate_qr(args.url, args.output, args.image, args.style, args.softness)


if __name__ == "__main__":
    main()
