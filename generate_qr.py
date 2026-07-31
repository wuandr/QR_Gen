import argparse
import sys

from qr_core import (
    BOX_SIZE_PRESETS,
    DEFAULT_SOFTNESS,
    DEFAULT_STYLE,
    QRGenerationError,
    QRRequest,
    SUPPORTED_STYLES,
    generate_qr_file,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a QR code from a URL.")
    parser.add_argument("url", help="The URL to encode in the QR code")
    parser.add_argument(
        "-o",
        "--output",
        default="qrcode.png",
        help="Output filename (default: qrcode.png). Format is inferred from the extension.",
    )
    parser.add_argument(
        "--image",
        help="Overlay image filename in project root (e.g. test_cat_face_1024.ppm).",
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
    parser.add_argument(
        "--size",
        choices=sorted(BOX_SIZE_PRESETS, key=BOX_SIZE_PRESETS.get),
        default="small",
        help=(
            "Output size for raster formats: small (~330px), medium (~660px), "
            "or large (~1320px) for a short URL. SVG output always scales."
        ),
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        result = generate_qr_file(
            QRRequest(
                url=args.url,
                output_path=args.output,
                overlay_path=args.image,
                style=args.style,
                softness=args.softness,
                overlay_scope="project_root",
                box_size=BOX_SIZE_PRESETS[args.size],
            )
        )
    except QRGenerationError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    for message in result.messages:
        print(message)
    print(f"QR code saved to: {result.output_path}")


if __name__ == "__main__":
    main()
