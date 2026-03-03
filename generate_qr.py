import argparse
import os
import sys
from pathlib import Path
import qrcode
import qrcode.image.svg
from PIL import Image


SUPPORTED_FORMATS = {"png", "jpeg", "jpg", "svg"}
MAX_OVERLAY_IMAGE_SIDE = 1024
INNER_FILL_RATIO = 1
KNOCKOUT_RATIO_CANDIDATES = (0.38, 0.36, 0.34, 0.32, 0.30, 0.28, 0.26, 0.24, 0.22, 0.20, 0.18)


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
        print(
            f"Error: image '{resolved.name}' is {width}x{height}. "
            f"Maximum supported size is {MAX_OVERLAY_IMAGE_SIDE}x{MAX_OVERLAY_IMAGE_SIDE}."
        )
        sys.exit(1)

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
) -> Image.Image:
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

    print("Error: no validated overlay size produced a scannable QR. Try a simpler image or shorter URL.")
    sys.exit(1)


def generate_qr(url: str, output: str, image_path: str | None) -> None:
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
        img = qrcode.make(url, image_factory=qrcode.image.svg.SvgImage)
        img.save(output)
    else:
        error_correction = qrcode.constants.ERROR_CORRECT_H if image_path else qrcode.constants.ERROR_CORRECT_M
        qr = qrcode.QRCode(error_correction=error_correction)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

        if overlay_img:
            img = place_largest_validated_overlay(
                qr_img=img,
                overlay_img=overlay_img,
                url=url,
                modules_count=qr.modules_count,
                box_size=qr.box_size,
                border=qr.border,
            )

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
            f"Max image size: {MAX_OVERLAY_IMAGE_SIDE}x{MAX_OVERLAY_IMAGE_SIDE}."
        ),
    )
    args = parser.parse_args()
    generate_qr(args.url, args.output, args.image)


if __name__ == "__main__":
    main()
