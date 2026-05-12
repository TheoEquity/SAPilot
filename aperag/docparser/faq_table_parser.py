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

"""FAQ table parser for docx files.

Parses FAQ documents where each FAQ entry is a table.
Uses MarkItDown for image extraction, then splits by FAQ ID boundaries.
Each FAQ entry becomes one complete chunk (no further splitting).
"""

import base64
import logging
import re
from hashlib import md5
from pathlib import Path
from typing import Any

from markitdown import MarkItDown

from aperag.docparser.base import AssetBinPart, BaseParser, FallbackError, MarkdownPart, Part

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = [".docx"]

# Pattern to match FAQ IDs in markdown table format: | FAQBASI0001 | Title |
FAQ_ID_PATTERN = re.compile(r"\|\s*(FAQ[A-Z]+\d+)\s*\|\s*(.*?)\s*\|")
FAQ_SECTION_TITLE_PATTERN = re.compile(r"^\s*[*-]\s*(?:\+\s*)?\d+[.、]\s+.+$", re.MULTILINE)


class FAQTableParser(BaseParser):
    """Parse FAQ docx where each table is one FAQ entry.
    
    Uses MarkItDown to extract content with images (as data URIs),
    then splits the full markdown by FAQ ID boundaries.
    """

    name = "faq_table"

    def supported_extensions(self) -> list[str]:
        return SUPPORTED_EXTENSIONS

    def parse_file(self, path: Path, metadata: dict[str, Any] = {}, **kwargs) -> list[Part]:
        # Use MarkItDown to get full markdown with data URI images
        mid = MarkItDown()
        result = mid.convert_local(str(path), keep_data_uris=True)
        full_markdown = result.markdown

        # Find all FAQ ID positions
        faq_matches = list(FAQ_ID_PATTERN.finditer(full_markdown))
        if len(faq_matches) < 2:
            raise FallbackError("Document does not match FAQ table format")

        section_starts = [match.start() for match in FAQ_SECTION_TITLE_PATTERN.finditer(full_markdown)]

        # Split markdown by FAQ ID boundaries
        parts: list[Part] = []
        for i, match in enumerate(faq_matches):
            start = match.start()
            # End is start of next FAQ or end of document
            if i + 1 < len(faq_matches):
                next_faq_start = faq_matches[i + 1].start()
                next_section_start = next((pos for pos in section_starts if start < pos < next_faq_start), None)
                end = next_section_start or next_faq_start
            else:
                end = len(full_markdown)

            faq_md = full_markdown[start:end].strip()
            faq_id = match.group(1)
            faq_title = match.group(2).strip()

            # Parse this FAQ entry
            entry_parts = self._parse_faq_entry(faq_md, faq_id, faq_title, metadata)
            parts.extend(entry_parts)

        logger.info(f"FAQTableParser: extracted {len(parts)} parts ({len(faq_matches)} FAQ entries) from {path.name}")
        return parts

    def _parse_faq_entry(
        self, faq_markdown: str, faq_id: str, faq_title: str, base_metadata: dict[str, Any]
    ) -> list[Part]:
        """Parse a single FAQ entry markdown into parts."""
        # Find and extract all data URI images
        data_uri_pattern = re.compile(r"!\[(.*?)\]\(\s*(data:.+?;base64,.+?)(?:\s+\"(.*?)\")?\s*\)")
        
        asset_parts: list[AssetBinPart] = []
        image_counter = 0

        def replace_data_uri(match):
            nonlocal image_counter
            alt_text = match.group(1) or ""
            data_uri = match.group(2)

            try:
                mime_type, encoded_data = data_uri.split("base64,")
                mime_type = mime_type[5:-1]  # Remove 'data:' and trailing ';'
                binary_data = base64.b64decode(encoded_data)

                asset_id = md5(binary_data).hexdigest()
                asset_parts.append(
                    AssetBinPart(
                        asset_id=asset_id,
                        data=binary_data,
                        mime_type=mime_type,
                        metadata={
                            **base_metadata,
                            "faq_id": faq_id,
                            "image_index": image_counter,
                            "vision_index": True,
                        },
                    )
                )
                image_counter += 1

                # Replace with asset URL reference
                return f"![{alt_text}](asset://{asset_id}?mime_type={mime_type})"
            except Exception as e:
                logger.warning(f"Error processing FAQ data URI: {e}")
                return match.group(0)

        # Replace data URIs with asset references
        cleaned_markdown = data_uri_pattern.sub(replace_data_uri, faq_markdown)

        # Create metadata for this FAQ entry
        entry_metadata = {
            **base_metadata,
            "faq_id": faq_id,
            "faq_title": faq_title,
            "chunk_type": "faq_entry",
            "source": "faq_table",
        }

        # Create MarkdownPart for the entire FAQ entry
        # Set content=markdown so rechunk can process it
        md_part = MarkdownPart(markdown=cleaned_markdown, metadata=entry_metadata)
        md_part.content = cleaned_markdown

        return [md_part] + asset_parts
