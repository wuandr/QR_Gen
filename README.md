# QR Code Generator

A simple Python script that generates a QR code from a URL and exports it as an image.

## Supported Formats

PNG, JPEG, SVG

## Setup

Create and activate a virtual environment, then install dependencies:

```bash
# Create the venv
python3 -m venv .venv

# Activate it
source .venv/bin/activate        # macOS/Linux
.venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

To deactivate the venv when you're done:

```bash
deactivate
```

## Usage

```bash
python generate_qr.py <url> [-o output_file] [--image filename]
```

| Flag | Description |
|------|-------------|
| `url` | The URL to encode |
| `-o` / `--output` | Output filename (default: `qrcode.png`). Format inferred from extension. |
| `--image` | Overlay an image from the project root (example: `test_cat_face_1024.ppm`). Max size: `1024x1024`. Uses adaptive sizing with decode validation and locks inner fill ratio to `0.9`. |

### Examples

```bash
# Default output (qrcode.png)
python generate_qr.py https://example.com

# With a project-root image in the centre
python generate_qr.py https://example.com --image test_cat_face_1024.ppm

# Custom filename — format is inferred from the extension
python generate_qr.py https://example.com -o mycode.png
python generate_qr.py https://example.com -o mycode.jpg
python generate_qr.py https://example.com -o mycode.svg
```

## Test Image

This repo includes `test_cat_face_1024.ppm`, a cute cat-face test image at the largest supported image size (`1024x1024`).

## Overlay Sizing

When `--image` is provided, the script now:
- Tries larger centre knockouts first.
- Decodes each candidate QR with OpenCV.
- Automatically backs off to the largest size that still decodes to the exact URL.
