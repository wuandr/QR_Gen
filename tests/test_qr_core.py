import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from qr_core import (
    DEFAULT_SOFTNESS,
    QRGenerationError,
    QRRequest,
    generate_qr_file,
    load_overlay_image,
)


class QRCoreTests(unittest.TestCase):
    def test_generate_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "code.png"
            result = generate_qr_file(QRRequest(url="https://example.com", output_path=output))
            self.assertEqual(result.output_format, "png")
            self.assertTrue(output.exists())
            self.assertEqual(result.messages, [])

    def test_generate_jpeg(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "code.jpg"
            result = generate_qr_file(
                QRRequest(
                    url="https://example.com/jpeg",
                    output_path=output,
                    style="rounded",
                    softness=0.4,
                )
            )
            self.assertEqual(result.output_format, "jpg")
            self.assertTrue(output.exists())

    def test_generate_svg_with_warning_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "code.svg"
            result = generate_qr_file(
                QRRequest(
                    url="https://example.com/svg",
                    output_path=output,
                    overlay_path="ignored.png",
                    style="rounded",
                )
            )
            self.assertTrue(output.exists())
            self.assertEqual(result.output_format, "svg")
            self.assertEqual(len(result.messages), 2)

    def test_invalid_softness_raises_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "code.png"
            with self.assertRaises(QRGenerationError):
                generate_qr_file(QRRequest(url="https://example.com", output_path=output, softness=1.0))

    def test_missing_overlay_image_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "code.png"
            with self.assertRaises(QRGenerationError):
                generate_qr_file(
                    QRRequest(
                        url="https://example.com",
                        output_path=output,
                        overlay_path="missing.png",
                        overlay_scope="any",
                    )
                )

    def test_large_overlay_is_downscaled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            overlay_path = tmp_path / "huge.png"
            Image.new("RGBA", (1800, 1200), "red").save(overlay_path)

            loaded = load_overlay_image(str(overlay_path), overlay_scope="any")

            self.assertLessEqual(loaded.image.size[0], 1024)
            self.assertLessEqual(loaded.image.size[1], 1024)
            self.assertTrue(any("downscaled image" in message for message in loaded.messages))

    def test_overlay_success_path_returns_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            overlay_path = tmp_path / "overlay.png"
            Image.new("RGBA", (256, 256), "blue").save(overlay_path)
            output = tmp_path / "code.png"

            with patch("qr_core.can_decode_to_url", side_effect=[True, True]):
                result = generate_qr_file(
                    QRRequest(
                        url="https://example.com/overlay",
                        output_path=output,
                        overlay_path=str(overlay_path),
                        overlay_scope="any",
                        softness=DEFAULT_SOFTNESS,
                    ),
                    include_preview=True,
                )

            self.assertTrue(output.exists())
            self.assertIsNotNone(result.preview_image)

    def test_overlay_failure_path_returns_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            overlay_path = tmp_path / "overlay.png"
            Image.new("RGBA", (256, 256), "black").save(overlay_path)
            output = tmp_path / "code.png"

            with patch("qr_core.can_decode_to_url", return_value=False):
                with self.assertRaises(QRGenerationError):
                    generate_qr_file(
                        QRRequest(
                            url="https://example.com/failure",
                            output_path=output,
                            overlay_path=str(overlay_path),
                            overlay_scope="any",
                        )
                    )


if __name__ == "__main__":
    unittest.main()
