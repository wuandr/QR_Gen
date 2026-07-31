# QR Code Generator

A cross-platform QR code generator with both a Python CLI and a Tkinter desktop GUI.

## Supported Formats

PNG, JPEG, SVG

## Setup

### Requirement: a Python with Tk 8.6

The desktop app needs a Python built against **Tk 8.6**. Two common interpreters will not work:

- Homebrew's `python@3.13`/`3.14` ship **no `_tkinter` at all** unless you also install the matching `python-tk` formula.
- macOS's own `/usr/bin/python3` links Apple's **Tk 8.5**, which hangs on window creation on recent macOS — the app starts but never draws.

Check before you build the venv:

```bash
python3 -c "import tkinter; print(tkinter.TkVersion)"   # must print 8.6
```

If it errors or prints 8.5, install a Tk-capable Python and build the venv from that interpreter:

```bash
brew install python@3.11 python-tk@3.11   # macOS
sudo apt install python3-tk               # Debian/Ubuntu
```

The CLI has no Tk requirement and runs on any Python 3.11+.

### Virtual environment

Create and activate a virtual environment, then install dependencies. A venv inherits Tk
from the interpreter it was created with, so create it with the Tk 8.6 Python you just checked:

```bash
# Create the venv
python3.11 -m venv .venv

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

## Desktop App

Launch the GUI:

```bash
python qr_gui.py
```

The GUI supports:
- **Live preview** — the code re-renders as you type, roughly 300ms after you stop. There is no Preview button and no stale-preview state.
- **Scan check** — every preview is decoded back and reports whether it scans.
- **Size** — Small / Medium / Large (about 330 / 660 / 1320 px for a short URL), with the exact output size shown under the preview. Defaults to Medium.
- **File format** — PNG, JPEG, or SVG. The format you pick decides what gets written, regardless of the extension you type in the save dialog.
- **Look** — square, dots, rounded, smooth, or diagonal modules, with a corner-rounding slider for the styles that use it.
- **Logo** — drop an image into the middle of the code from anywhere on disk. The app finds the largest placement that still scans.
- **Languages** — English and 繁體中文 (Traditional Chinese, Taiwan). Switch from the picker at the top right of the window or the Language menu; either updates the whole interface immediately. The choice is remembered in `~/.qr_generator.json`.

Keyboard: `Cmd/Ctrl+S` saves, `Cmd/Ctrl+R` starts over, `Return` saves, `Esc` clears focus.

Previews always render at a small fixed size and are scaled up only on save, so
changing Size never slows down typing.

### Adding a language

All user-visible text lives in [`i18n.py`](i18n.py), keyed by stable string IDs.
To add a language, add one table to `STRINGS` and one entry to `LANGUAGES`;
`tests/test_i18n.py` checks that every language covers every ID and uses the same
named placeholders.

Tk draws characters its font does not cover as empty boxes rather than falling
back, so `CJK_FONT_CANDIDATES` in [`qr_gui.py`](qr_gui.py) names a per-platform
font for Chinese/Japanese/Korean (PingFang TC on macOS, Microsoft JhengHei UI on
Windows, Noto Sans CJK on Linux). The first installed candidate is applied on
switching and the platform default is restored on switching back. If a language
needs a script the default UI font lacks, add candidates there too — and note
that a minimal Linux image may have none of them installed, in which case the
text still renders as boxes.

## CLI Usage

```bash
python generate_qr.py <url> [-o output_file] [--image filename] [--style square|rounded|dot|smooth|diag_rounded] [--softness 0.35] [--size small|medium|large]
```

| Flag | Description |
|------|-------------|
| `url` | The URL to encode |
| `-o` / `--output` | Output filename (default: `qrcode.png`). Format inferred from extension. |
| `--image` | Overlay an image from the project root (example: `test_cat_face_1024.ppm`). Max size: `1024x1024` with auto-downscaling. Uses adaptive sizing with decode validation and locks inner fill ratio to `1`. |
| `--style` | Raster module style: `square` (default), `rounded`, `dot`, `smooth`, `diag_rounded` (only top-right and bottom-left corners rounded). Finder patterns stay square for scan reliability. |
| `--softness` | Corner softness for `rounded`/`smooth`/`diag_rounded` styles in `[0.0, 0.5]` (default: `0.35`). |
| `--size` | Raster output size: `small` (default, ~330px), `medium` (~660px), `large` (~1320px) for a short URL. SVG output is vector and ignores this. The CLI default stays `small` for backwards compatibility; the desktop app defaults to `medium`. |

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

# Soften module corners
python generate_qr.py https://example.com -o mycode_rounded.png --style rounded --softness 0.4

# Connected soft corners (fewer isolated gaps than plain rounded)
python generate_qr.py https://example.com -o mycode_smooth.png --style smooth --softness 0.35

# Only top-right and bottom-left corners rounded per module (with smooth joining)
python generate_qr.py https://example.com -o mycode_diag_rounded.png --style diag_rounded --softness 0.4

# Larger output for print
python generate_qr.py https://example.com -o flyer.png --size large
```

## Test Image

This repo includes `test_cat_face_1024.ppm`, a test image at the largest supported image size (`1024x1024`).

## Overlay Sizing

When `--image` is provided, the script now:
- Tries larger centre knockouts first.
- Decodes each candidate QR with OpenCV.
- Auto-adjusts quiet-zone border for OpenCV decode stability when needed.
- Automatically backs off to the largest size that still decodes to the exact URL.

## Packaging

Build the desktop app with PyInstaller:

```bash
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean qr_gui.spec
```

Artifacts are created in `dist/`:
- Linux: `dist/QR_Generator/`
- Windows: `dist/QR_Generator/`
- macOS: `dist/QR_Generator.app`

GitHub Actions builds GUI artifacts for Linux x64, Windows x64, and macOS Apple Silicon using `.github/workflows/build-gui.yml`.
