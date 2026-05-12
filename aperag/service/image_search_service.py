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
import logging
import re
from typing import List, Optional

from aperag.config import settings
from aperag.context.context import ContextManager
from aperag.db.ops import async_db_ops
from aperag.llm.embed.base_embedding import get_collection_embedding_service_sync
from aperag.llm.llm_error_types import EmbeddingError, ProviderNotFoundError
from aperag.objectstore.base import get_object_store
from aperag.query.query import DocumentWithScore
from aperag.schema import view_models
from aperag.service.document_service import document_service
from aperag.utils.utils import generate_vector_db_collection_name

logger = logging.getLogger(__name__)


class ImageSearchService:
    """Search knowledge-base vision indexes with uploaded image attachments."""

    def __init__(self):
        self.db_ops = async_db_ops

    async def build_chat_image_search_context(
        self,
        user_id: str,
        chat_id: str,
        files: Optional[List[view_models.File]],
        collections: List[view_models.Collection],
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
    ) -> str:
        if not files or not collections:
            return ""

        top_k = top_k or settings.dingtalk_image_search_topk
        similarity_threshold = similarity_threshold or settings.dingtalk_image_search_similarity
        contexts: List[DocumentWithScore] = []
        for file in files:
            try:
                data_uri = await self._load_chat_image_as_data_uri(user_id, chat_id, file.id)
                if not data_uri:
                    continue
                results = await self.search_similar_images(
                    user_id=user_id,
                    collections=collections,
                    image_data_uri=data_uri,
                    top_k=top_k,
                    similarity_threshold=similarity_threshold,
                )
                logger.info("Chat image search returned %s results for document=%s", len(results), file.id)
                contexts.extend(results)
            except Exception:
                logger.exception("Failed to build chat image search context for document=%s", file.id)

        return await self.format_image_search_context(user_id, contexts, top_k=top_k)

    async def _load_chat_image_as_data_uri(self, user_id: str, chat_id: str, document_id: Optional[str]) -> str:
        if not document_id:
            return ""

        document = await self.db_ops.query_document_by_id(document_id)
        if not document:
            return ""
        if not await self._is_chat_document(document, user_id, chat_id):
            return ""
        if not self._is_image_document(document):
            return ""

        object_path = self._get_document_object_path(document)
        if not object_path:
            return ""

        obj = get_object_store().get(object_path)
        if obj is None:
            return ""
        with obj:
            content = obj.read()

        if not content:
            return ""
        content_type = self._guess_image_content_type(content, document.name)
        encoded = base64.b64encode(content).decode("utf-8")
        return f"data:{content_type};base64,{encoded}"

    def _get_document_object_path(self, document) -> str:
        if document.object_path:
            return document.object_path
        if not document.doc_metadata:
            return ""
        try:
            metadata = json.loads(document.doc_metadata)
        except json.JSONDecodeError:
            return ""
        return str(metadata.get("object_path") or "")

    async def _is_chat_document(self, document, user_id: str, chat_id: str) -> bool:
        if document.user != user_id or not document.doc_metadata:
            return False
        try:
            metadata = json.loads(document.doc_metadata)
        except json.JSONDecodeError:
            return False
        return metadata.get("file_type") == "chat_upload" and metadata.get("chat_id") == chat_id

    def _is_image_document(self, document) -> bool:
        name = (document.name or "").lower()
        return name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"))

    def _guess_image_content_type(self, content: bytes, filename: str = "") -> str:
        name = (filename or "").lower()
        if content.startswith(b"\xff\xd8\xff") or name.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        if content.startswith(b"\x89PNG\r\n\x1a\n") or name.endswith(".png"):
            return "image/png"
        if content.startswith(b"GIF87a") or content.startswith(b"GIF89a") or name.endswith(".gif"):
            return "image/gif"
        if (content.startswith(b"RIFF") and b"WEBP" in content[:16]) or name.endswith(".webp"):
            return "image/webp"
        if content.startswith(b"BM") or name.endswith(".bmp"):
            return "image/bmp"
        return "image/png"

    async def search_similar_images(
        self,
        user_id: str,
        collections: List[view_models.Collection],
        image_data_uri: str,
        top_k: int,
        similarity_threshold: float,
    ) -> List[DocumentWithScore]:
        results: List[DocumentWithScore] = []
        for collection_view in collections:
            collection_id = collection_view.id
            if not collection_id:
                continue
            collection = await self.db_ops.query_collection(user_id, collection_id)
            if not collection:
                continue
            try:
                embedding_model, _ = get_collection_embedding_service_sync(collection)
                if not embedding_model.is_multimodal():
                    logger.info("Image search skipped non-multimodal collection %s", collection_id)
                    continue
                vector = embedding_model.embed_query(image_data_uri)
                collection_name = generate_vector_db_collection_name(collection.id)
                vectordb_ctx = json.loads(settings.vector_db_context)
                vectordb_ctx["collection"] = collection_name
                context_manager = ContextManager(collection_name, embedding_model, settings.vector_db_type, vectordb_ctx)
                collection_results = context_manager.query(
                    "uploaded_chat_image",
                    score_threshold=similarity_threshold,
                    topk=max(top_k * 2, top_k),
                    vector=vector,
                    index_types=["vision"],
                )
                logger.info(
                    "Image search collection=%s raw_results=%s top_score=%s",
                    collection_id,
                    len(collection_results),
                    collection_results[0].score if collection_results else None,
                )
                for item in collection_results:
                    if item.metadata is None:
                        item.metadata = {}
                    item.metadata["recall_type"] = "vision_search"
                    item.metadata["collection_title"] = collection_view.title or collection.title
                results.extend(collection_results)
            except (ProviderNotFoundError, EmbeddingError) as e:
                logger.warning("Image search skipped for collection %s: %s", collection_id, e)
            except Exception:
                logger.exception("Image search failed for collection %s", collection_id)

        results.sort(key=lambda item: item.score if item.score is not None else 0, reverse=True)
        return self._deduplicate_image_results(results)[:top_k]

    def _deduplicate_image_results(self, results: List[DocumentWithScore]) -> List[DocumentWithScore]:
        seen = set()
        deduplicated = []
        for item in results:
            metadata = item.metadata or {}
            key = (metadata.get("collection_id"), metadata.get("document_id"), metadata.get("asset_id"))
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(item)
        return deduplicated

    async def format_image_search_context(
        self,
        user_id: str,
        results: List[DocumentWithScore],
        top_k: Optional[int] = None,
    ) -> str:
        if not results:
            return ""

        top_k = top_k or settings.dingtalk_image_search_topk
        enriched_results = await self._enrich_results_with_faq_chunks(user_id, self._deduplicate_image_results(results))
        lines = [
            "相似报错截图主候选：",
            "请优先按照第 1 条候选 FAQ 回答；候选内容不足时，再结合用户问题做谨慎补充。",
        ]
        for idx, item in enumerate(enriched_results[:top_k], start=1):
            metadata = item.metadata or {}
            score = f"{item.score:.3f}" if isinstance(item.score, (int, float)) else "未知"
            source = metadata.get("source") or metadata.get("name") or "未知来源"
            collection_title = metadata.get("collection_title") or metadata.get("collection_id") or "未知知识库"
            asset_id = metadata.get("asset_id") or ""
            document_id = metadata.get("document_id") or ""
            faq_id = metadata.get("faq_id") or ""
            content = (item.text or "").strip()
            if len(content) > 900:
                content = content[:900] + "..."
            lines.append(
                f"{idx}. 相似度 {score}，知识库：{collection_title}，来源：{source}，FAQ：{faq_id}，document_id：{document_id}，asset_id：{asset_id}"
            )
            if content:
                lines.append(f"候选 FAQ 内容：{content}")
        return "\n".join(lines)

    async def _enrich_results_with_faq_chunks(
        self,
        user_id: str,
        results: List[DocumentWithScore],
    ) -> List[DocumentWithScore]:
        chunk_cache = {}
        enriched = []
        for item in results:
            metadata = item.metadata or {}
            collection_id = metadata.get("collection_id")
            document_id = metadata.get("document_id")
            asset_id = metadata.get("asset_id")
            if not collection_id or not document_id or not asset_id:
                enriched.append(item)
                continue

            cache_key = (collection_id, document_id)
            if cache_key not in chunk_cache:
                try:
                    chunk_cache[cache_key] = await document_service.get_document_chunks(user_id, collection_id, document_id)
                except Exception:
                    logger.exception("Failed to load chunks for image search enrichment document=%s", document_id)
                    chunk_cache[cache_key] = []

            matched_chunk = self._find_chunk_by_asset_id(chunk_cache[cache_key], asset_id)
            if matched_chunk:
                item.text = matched_chunk.text or item.text
                item.metadata = {**metadata, **(matched_chunk.metadata or {})}
                item.metadata["asset_id"] = asset_id
                item.metadata["collection_id"] = collection_id
                item.metadata["document_id"] = document_id
                faq_id = self._extract_faq_id(item.text or "")
                if faq_id:
                    item.metadata["faq_id"] = faq_id
            enriched.append(item)
        return enriched

    def _find_chunk_by_asset_id(self, chunks: List[view_models.Chunk], asset_id: str) -> Optional[view_models.Chunk]:
        marker = f"asset://{asset_id}"
        for chunk in chunks:
            if marker in (chunk.text or ""):
                return chunk
        return None

    def _extract_faq_id(self, text: str) -> str:
        match = re.search(r"FAQ[A-Z]+\d+", text or "")
        return match.group(0) if match else ""


image_search_service = ImageSearchService()
