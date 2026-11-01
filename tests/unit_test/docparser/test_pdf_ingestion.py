from types import SimpleNamespace

import pytest

from aperag.docparser.base import AssetBinPart, MarkdownPart, TextPart
from aperag.docparser.chunking import rechunk


def make_pdf(path):
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 7 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length 43 >>\nstream\nBT /F1 12 Tf 20 140 Td (TextOne) Tj ET\nendstream",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>",
        b"<< /Length 43 >>\nstream\nBT /F1 12 Tf 20 140 Td (TextTwo) Tj ET\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    data = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 8\n0000000000 65535 f \n"
    data += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    data += f"trailer\n<< /Size 8 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(data)
    return path


def test_pdf_text_images_ocr_and_page_association(tmp_path, monkeypatch):
    from aperag.docparser import pdf_parser

    path = make_pdf(tmp_path / "two-pages.pdf")
    monkeypatch.setattr(pdf_parser.shutil, "which", lambda x: "tesseract")
    calls = []

    def ocr(cmd, **kwargs):
        assert kwargs["input"].startswith(b"\x89PNG")
        calls.append(cmd)
        return SimpleNamespace(stdout="Screenshot-only BUDGET9C".encode(), returncode=0, stderr=b"")

    monkeypatch.setattr(pdf_parser.subprocess, "run", ocr)
    parts = pdf_parser.PdfParser().parse_file(path, {"doc_id": "sample"})
    assets = [p for p in parts if isinstance(p, AssetBinPart)]
    text = [p for p in parts if isinstance(p, TextPart)]
    markdown = "\n".join(p.markdown for p in parts if isinstance(p, MarkdownPart))
    assert len(assets) == len(text) == len(calls) == 2
    assert "TextOne" in text[0].content and "TextTwo" in text[1].content
    assert "Screenshot-only BUDGET9C" in text[0].content
    for i, (asset, part) in enumerate(zip(assets, text)):
        assert asset.metadata["page_idx"] == part.metadata["page_idx"] == i
        assert part.metadata["asset_id"] == asset.asset_id
        assert f"asset://{asset.asset_id}" in markdown
        assert part.metadata["pdf_source_map"][0]["page_idx"] == i
    chunks = rechunk(text, 1000, 0, lambda s: list(s))
    assert len(chunks) == 2
    assert [c.metadata["page_idx"] for c in chunks] == [0, 1]


def test_pdf_missing_ocr_dependency_is_not_reported_as_success(tmp_path, monkeypatch):
    from aperag.docparser import pdf_parser

    monkeypatch.setattr(pdf_parser.shutil, "which", lambda x: None)
    with pytest.raises(RuntimeError, match="tesseract"):
        pdf_parser.PdfParser().parse_file(make_pdf(tmp_path / "sample.pdf"))


def test_pdf_ocr_failure_does_not_drop_screenshot_text_silently(tmp_path, monkeypatch):
    from aperag.docparser import pdf_parser

    monkeypatch.setattr(pdf_parser.shutil, "which", lambda x: "tesseract")

    def fail(*args, **kwargs):
        raise pdf_parser.subprocess.TimeoutExpired("tesseract", 120)

    monkeypatch.setattr(pdf_parser.subprocess, "run", fail)
    with pytest.raises(pdf_parser.subprocess.TimeoutExpired):
        pdf_parser.PdfParser().parse_file(make_pdf(tmp_path / "sample.pdf"))
