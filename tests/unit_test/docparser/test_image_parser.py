import shutil
import subprocess
from types import SimpleNamespace

import pytest
from PIL import Image, ImageDraw, ImageFont

from aperag.docparser.base import FallbackError, TextPart
from aperag.docparser.image_parser import ImageParser


@pytest.fixture
def screenshot(tmp_path):
    path = tmp_path / "input.png"
    image = Image.new("RGB", (1000, 180), "white")
    font = ImageFont.truetype("DejaVuSans.ttf", 48)
    ImageDraw.Draw(image).text((30, 40), "SAP ME21N M7 021", fill="black", font=font)
    image.save(path)
    return path


def test_unconfigured_paddle_uses_existing_local_ocr(monkeypatch, screenshot):
    if shutil.which("tesseract") is None:
        pytest.skip("Local OCR runtime is not installed")
    monkeypatch.setattr("aperag.docparser.image_parser.settings.paddleocr_host", None)
    metadata = {"document_id": "document-test"}

    parts = ImageParser().parse_file(screenshot, metadata)

    assert len(parts) == 1
    assert isinstance(parts[0], TextPart)
    assert "SAP ME21N M7 021" in parts[0].content
    assert parts[0].metadata["document_id"] == "document-test"
    assert "md_source_map" in parts[0].metadata
    assert metadata == {"document_id": "document-test"}


def test_read_image_text_uses_local_ocr_without_paddle(monkeypatch, screenshot):
    if shutil.which("tesseract") is None:
        pytest.skip("Local OCR runtime is not installed")
    monkeypatch.setattr("aperag.docparser.image_parser.settings.paddleocr_host", None)

    assert "ME21N" in ImageParser().read_image_text(screenshot)


def test_missing_local_ocr_remains_an_explicit_parser_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr("aperag.docparser.image_parser.settings.paddleocr_host", None)
    monkeypatch.setattr(shutil, "which", lambda name: None)

    with pytest.raises(FallbackError, match="tesseract"):
        ImageParser().parse_file(tmp_path / "input.png")


def test_configured_paddle_keeps_existing_ocr_path(monkeypatch, screenshot):
    monkeypatch.setattr("aperag.docparser.image_parser.settings.paddleocr_host", "http://ocr.local")
    monkeypatch.setattr(
        "aperag.docparser.image_parser.requests.post",
        lambda **kwargs: SimpleNamespace(text='{"results": [[{"text": "SAP"}, {"text": " M7 021"}]]}'),
    )

    assert ImageParser().parse_file(screenshot)[0].content == "SAP M7 021"


def test_failed_local_ocr_reports_fallback(monkeypatch, screenshot):
    monkeypatch.setattr("aperag.docparser.image_parser.settings.paddleocr_host", None)
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/tesseract")

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], stderr=b"missing language data")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(FallbackError, match="tesseract"):
        ImageParser().read_image_text(screenshot)
