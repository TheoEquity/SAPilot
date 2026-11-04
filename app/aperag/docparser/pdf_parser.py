# Copyright 2025 ApeCloud, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import io
import logging
import shutil
import subprocess
from contextlib import closing
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium

from aperag.docparser.base import AssetBinPart, BaseParser, MarkdownPart, Part, PdfPart, TextPart
from aperag.docparser.utils import asset_bin_part_to_url

logger = logging.getLogger(__name__)

class PdfParser(BaseParser):
    """Keep PDF text, screenshot text and the original page layout together."""

    name = "pdf"

    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    def parse_file(self, path: Path, metadata: dict[str, Any] | None = None, **kwargs) -> list[Part]:
        tesseract = shutil.which("tesseract")
        if tesseract is None:
            raise RuntimeError("PDF screenshot extraction requires tesseract with chi_sim and eng language data")

        data = path.read_bytes()
        parts: list[Part] = [PdfPart(data=data, metadata={"page_images_extracted": True})]
        with closing(pdfium.PdfDocument(data)) as doc:
            for page_idx in range(len(doc)):
                with closing(doc[page_idx]) as page:
                    with closing(page.get_textpage()) as textpage:
                        text = textpage.get_text_range(count=textpage.count_chars()).replace("\r\n", "\n")
                    # 180 DPI keeps small SAP UI labels readable in the source page image.
                    bitmap = page.render(scale=2.5)
                    try:
                        image = bitmap.to_pil()
                        try:
                            with io.BytesIO() as buffer:
                                image.save(buffer, format="PNG")
                                png = buffer.getvalue()
                        finally:
                            image.close()
                    finally:
                        bitmap.close()
                    result = subprocess.run(
                        [tesseract, "stdin", "stdout", "-l", "chi_sim+eng"],
                        input=png,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True,
                        timeout=120,
                    )
                    ocr = result.stdout.decode("utf-8").strip()
                    asset_id = f"page_{page_idx}.png"
                    meta = dict(metadata or {})
                    meta.update(
                        page_idx=page_idx,
                        asset_id=asset_id,
                        converted_from="pdf",
                        vision_index=True,
                        chunk_type="pdf_page",
                        pdf_source_map=[{"page_idx": page_idx, "bbox": [0, 0, *page.get_size()]}],
                    )
                    asset = AssetBinPart(asset_id=asset_id, data=png, mime_type="image/png", metadata=meta.copy())
                    content = f"## PDF 第 {page_idx + 1} 页\n\n{text.strip()}"
                    if ocr:
                        content += f"\n\n### 图片文字识别（可能有误，请核对原页图）\n\n{ocr}"
                    content += f"\n\n![PDF 第 {page_idx + 1} 页]({asset_bin_part_to_url(asset)})"
                    # Markdown is for preview; TextPart supplies both regular indexes.
                    parts.extend(
                        [
                            MarkdownPart(markdown=content, metadata=meta.copy()),
                            asset,
                            TextPart(content=content, metadata=meta.copy()),
                        ]
                    )
            logger.info("pdf.pages.extracted", extra={"page_count": len(doc), "image_count": len(doc)})
        return parts
