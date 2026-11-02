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

import base64
import json
import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from aperag.config import settings
from aperag.docparser.base import BaseParser, FallbackError, Part, TextPart

SUPPORTED_EXTENSIONS = [
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".tiff",
    ".tif",
]


class ImageParser(BaseParser):
    name = "image"

    def supported_extensions(self) -> list[str]:
        return SUPPORTED_EXTENSIONS

    def parse_file(self, path: Path, metadata: dict[str, Any] = {}, **kwargs) -> list[Part]:
        content = self.read_image_text(path)
        metadata = metadata.copy()
        metadata["md_source_map"] = [0, content.count("\n") + 1]
        return [TextPart(content=content, metadata=metadata)]

    def read_image_text(self, path: Path) -> str:
        if not settings.paddleocr_host:
            tesseract = shutil.which("tesseract")
            if tesseract is None:
                raise FallbackError("Image OCR requires PADDLEOCR_HOST or local tesseract with chi_sim and eng data")
            try:
                result = subprocess.run(
                    [tesseract, "stdin", "stdout", "-l", "chi_sim+eng"],
                    input=path.read_bytes(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=120,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise FallbackError("Local tesseract image OCR failed") from exc
            return result.stdout.decode("utf-8").strip()

        def image_to_base64(image_path: str):
            with Image.open(image_path) as image:
                if image.mode == "RGBA":
                    image = image.convert("RGB")
                buffered = BytesIO()
                image.save(buffered, format="JPEG")
                img_byte = buffered.getvalue()
                img_base64 = base64.b64encode(img_byte)
                return img_base64.decode()

        data = {"images": [image_to_base64(str(path))]}
        headers = {"Content-type": "application/json"}
        url = settings.paddleocr_host + "/predict/ocr_system"
        r = requests.post(url=url, headers=headers, data=json.dumps(data))
        data = json.loads(r.text)

        # TODO: extract image metadata by using exiftool

        texts = [item["text"] for group in data["results"] for item in group if "text" in item]
        res = ""
        for text in texts:
            res += text
        return res
