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

import json
import logging
import os
import re
from typing import Any, Dict

import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from aperag.agent.tool_reference_extractor import _format_reference_content
from aperag.db.ops import async_db_ops

# Import view models for type safety
from aperag.schema.view_models import (
    Collection,
    CollectionViewList,
    SearchResult,
    SearchResultItem,
    WebReadResponse,
    WebSearchResponse,
)
from aperag.service.chat_collection_service import chat_collection_service
from aperag.service.image_search_service import image_search_service

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp_server = FastMCP("ApeRAG")

# Base URL for internal API calls
API_BASE_URL = "http://localhost:8000"


def _limit_search_results(search_result: SearchResult, topk: int) -> None:
    """Keep the documented per-index limit without dropping another index's results."""
    counts = {}
    items = []
    for item in search_result.items or []:
        source = item.recall_type or "unknown"
        if counts.get(source, 0) >= topk:
            continue
        counts[source] = counts.get(source, 0) + 1
        item.rank = len(items) + 1
        items.append(item)
    search_result.items = items


def _scope_search_sources(search_result: SearchResult, collection_id: str) -> None:
    for item in search_result.items or []:
        metadata = item.metadata or {}
        metadata['collection_id'] = collection_id
        metadata['document_id'] = metadata.get('document_id') or metadata.get('doc_id')
        if isinstance(metadata.get('page_idx'), int):
            metadata['physical_page'] = metadata['page_idx'] + 1
        if metadata.get('asset_id'):
            metadata['asset_url'] = _format_reference_content('asset://' + metadata['asset_id'], metadata)
        item.content = _format_reference_content(item.content or '', metadata)
        item.metadata = metadata


def _pdf_faq_page_sections(markdown: str, headings: list) -> dict:
    """Describe explicit native FAQ boundaries; never infer them from OCR or a TOC."""
    pages = {}
    previous = None
    for index, page_heading in enumerate(headings):
        page = int(page_heading.group(1)) - 1
        end = headings[index + 1].start() if index + 1 < len(headings) else len(markdown)
        content = markdown[page_heading.start():end]
        native = content.split("### 图片文字识别", 1)[0]
        titles = list(re.finditer(r"(?m)^\d+(?:\.\d+){1,5}\.?[ \t]+[^\n]+", native))
        markers = list(re.finditer(r"(?m)^(FAQ[A-Z0-9]+)\b[^\n]*", native))
        explicit = []
        for marker in markers:
            title = next((t for t in reversed(titles) if t.start() < marker.start()), None)
            if title is None or native[title.end():marker.start()].count("\n") > 5:
                continue
            next_title = next((t.start() for t in titles if t.start() > marker.start()), len(native))
            # A directory entry lacks a native problem body. OCR repeats are excluded above.
            if not re.search(r"问题描述[：:]", native[marker.end():next_title]):
                continue
            explicit.append({"faq_id": marker.group(1), "relation": "starts_on_page",
                             "source_start": title.start(), "source_end": next_title,
                             "heading_page_idx": page})
        if explicit:
            sections = []
            prefix = native[:explicit[0]["source_start"]]
            continuation = re.search(r"(?m)^(?:解决方案|问题描述)[：:]", prefix)
            if previous and continuation:
                sections.append({"faq_id": previous[0], "relation": "continues_previous_page",
                                 "source_start": continuation.start(), "source_end": len(prefix),
                                 "heading_page_idx": previous[1]})
            sections.extend(explicit)
            pages[page] = sections
            previous = (explicit[-1]["faq_id"], page)
        else:
            previous = None
    return pages


def _mark_pdf_faq_sections(text: str, source_length: int, offset: int, sections: list) -> tuple:
    """Add clearly separate display markers while retaining raw-source offset mapping."""
    parts, markers = [], []
    cursor = 0
    display_length = 0
    for section in sections:
        if section["source_end"] <= offset or section["source_start"] >= offset + len(text):
            continue
        position = max(0, section["source_start"] - offset)
        fragment = text[cursor:position]
        parts.append(fragment)
        display_length += len(fragment)
        label = "续上页：" if section["relation"] == "continues_previous_page" else "新条目："
        marker = ("\n【上下文边界（系统标识，非原文）：" + label + section["faq_id"]
                  + f"；本页原文字符[{section['source_start']},{section['source_end']})】\n")
        markers.append({"text": marker, "display_start": display_length,
                        "display_end": display_length + len(marker), "source_offset": offset + position})
        parts.append(marker)
        display_length += len(marker)
        cursor = position
    parts.append(text[cursor:])
    return "".join(parts), {"basis": "explicit_native_section_heading_and_faq_marker",
                            "source_characters": source_length, "returned_source_offset": offset,
                            "sections": sections, "display_markers": markers}


async def _read_document_context(
    api_key: str,
    collection_id: str,
    document_id: str,
    query: str,
    page_idx: int | None,
    offset: int,
    image_asset_ids: list[str] | None = None,
) -> Dict[str, Any]:
    # Reuse the preview API's authenticated document+collection+owner check. Never
    # accept an object-store path from the caller or read the store directly.
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(
            f"{API_BASE_URL}/api/v1/collections/{collection_id}/documents/{document_id}/preview",
            headers={"Authorization": f"Bearer {api_key}"},
        )
    if response.status_code != 200:
        return {"error": f"Document context unavailable: {response.status_code}"}

    preview = response.json()
    markdown = preview.get("markdown_content") or ""
    chunks = preview.get("chunks") or []
    source = preview.get("doc_filename") or ""
    available_assets = set(re.findall(r"asset://([^?\s)]+)", markdown))
    available_assets.update((chunk.get("metadata") or {}).get("asset_id") for chunk in chunks)
    if image_asset_ids and (
        len(image_asset_ids) > 6
        or any(
            not re.fullmatch(r"[A-Za-z0-9_.-]+", asset_id) or asset_id not in available_assets
            for asset_id in image_asset_ids
        )
    ):
        return {"error": "image_asset_ids must contain at most six asset IDs present in this document preview"}
    sections = []
    faq_sections = {}
    if page_idx is not None:
        # These headings are emitted by PdfParser; physical page indexes stay
        # separate even when a FAQ continues onto the next page.
        headings = list(re.finditer(r"(?m)^## PDF 第 (\d+) 页\s*$", markdown))
        if headings:
            faq_sections = _pdf_faq_page_sections(markdown, headings)
            if page_idx not in {int(heading.group(1)) - 1 for heading in headings}:
                return {"error": "Requested physical page does not exist in this document"}
            for index, heading in enumerate(headings):
                page = int(heading.group(1)) - 1
                if abs(page - page_idx) > 1:
                    continue
                end = headings[index + 1].start() if index + 1 < len(headings) else len(markdown)
                metadata = next(
                    (
                        dict(c.get("metadata") or {})
                        for c in chunks
                        if (c.get("metadata") or {}).get("page_idx") == page
                    ),
                    {},
                )
                metadata["page_idx"] = page
                sections.append((markdown[heading.start() : end], metadata))
        else:
            if not any((chunk.get("metadata") or {}).get("page_idx") == page_idx for chunk in chunks):
                return {"error": "Requested physical page does not exist in this document"}
            for chunk in chunks:
                metadata = dict(chunk.get("metadata") or {})
                page = metadata.get("page_idx")
                if isinstance(page, int) and abs(page - page_idx) <= 1:
                    sections.append((chunk.get("text") or "", metadata))
            sections.sort(key=lambda section: section[1]["page_idx"])
        if not sections:
            return {"error": "No indexed physical page context found for the requested page"}
    else:
        # The original parsed markdown retains section/table order, which cannot
        # be reconstructed reliably from scored or deduplicated search hits.
        if not markdown:
            markdown = "\n\n".join(c.get("text") or "" for c in chunks)
        sections = [(markdown, {})]

    total_chars = sum(len(content) for content, _ in sections)
    if offset > total_chars:
        return {"error": "context_offset exceeds the document context length"}
    remaining = 48000
    skipped = 0
    returned_chars = 0
    items = []
    for content, metadata in sections:
        section_start = max(0, offset - skipped)
        skipped += len(content)
        if section_start >= len(content) or remaining <= 0:
            continue
        text = content[section_start : section_start + remaining]
        source_chars = len(text)
        if faq_sections.get(metadata.get("page_idx")):
            text, metadata["faq_context"] = _mark_pdf_faq_sections(
                text, len(content), section_start, faq_sections[metadata["page_idx"]]
            )
        # Do not expose internal storage paths through the context interface.
        metadata.pop("object_path", None)
        metadata.update(collection_id=collection_id, document_id=document_id, source=source, document_context=True)
        if metadata.get("chunk_type") == "pdf_page" and metadata.get("asset_id"):
            metadata["mimetype"] = "image/png"
        items.append(
            SearchResultItem(
                rank=len(items) + 1, content=text, source=source, recall_type="fulltext_search", metadata=metadata
            )
        )
        remaining -= source_chars
        returned_chars += source_chars
    next_offset = offset + returned_chars
    source_result = SearchResult(query=query, items=items)
    _scope_search_sources(source_result, collection_id)
    result = source_result.model_dump()
    result["context"] = {
        "document_id": document_id,
        "page_idx": page_idx,
        "page_radius": 1 if page_idx is not None else None,
        "offset": offset,
        "total_chars": total_chars,
        "truncated": next_offset < total_chars,
        "next_offset": next_offset if next_offset < total_chars else None,
    }
    if image_asset_ids:
        from aperag.service.visual_context_service import describe_document_images

        api_key_record = await async_db_ops.get_api_key_by_key(api_key)
        if not api_key_record:
            return {"error": "Unauthorized API key"}
        result["context"]["visual_observations"] = await describe_document_images(
            api_key_record.user, collection_id, document_id, query, image_asset_ids
        )
    return result


def _is_image_filename(name: str) -> bool:
    return str(name or "").lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"))


async def _resolve_current_chat_image_document_id(user_id: str, chat_id: str, file_id: str) -> str:
    """Resolve the current chat turn's uploaded image document ID.

    Order:
    1. Use the explicit persisted document ID when provided.
    2. Otherwise, scan current chat-upload documents for this chat and pick the latest
       associated image document. This matches the current turn because document
       association happens before the MCP tool is invoked.
    """
    if file_id:
        document = await async_db_ops.query_document_by_id(file_id)
        if document and _is_image_filename(getattr(document, "name", "")):
            return file_id

    chat_collection = await chat_collection_service.get_user_chat_collection(user_id)
    if not chat_collection:
        return ""

    documents = await async_db_ops.query_documents([user_id], chat_collection.id)
    matched_documents = []
    for document in documents or []:
        if not _is_image_filename(getattr(document, "name", "")):
            continue
        if not document.doc_metadata:
            continue
        try:
            metadata = json.loads(document.doc_metadata)
        except json.JSONDecodeError:
            continue
        if metadata.get("file_type") != "chat_upload":
            continue
        if metadata.get("chat_id") != chat_id:
            continue
        if not metadata.get("message_id"):
            continue
        matched_documents.append((document, metadata))

    if not matched_documents:
        return ""

    matched_documents.sort(
        key=lambda item: (
            item[1].get("updated_at") or "",
            item[0].gmt_updated.isoformat() if getattr(item[0], "gmt_updated", None) else "",
            item[0].gmt_created.isoformat() if getattr(item[0], "gmt_created", None) else "",
        ),
        reverse=True,
    )
    return matched_documents[0][0].id


@mcp_server.tool
async def list_collections() -> Dict[str, Any]:
    """List all collections available to the user.

    Returns:
        List of collections with only essential information (id, title, description)
        for security and optimized LLM search.

    Note:
        Uses CollectionViewList view model for type-safe response parsing but filters
        sensitive and unnecessary information.
    """
    try:
        api_key = get_api_key()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{API_BASE_URL}/api/v1/collections", headers={"Authorization": f"Bearer {api_key}"}
            )
            if response.status_code == 200:
                try:
                    # Parse response using view model for type safety
                    collection_list = CollectionViewList.model_validate(response.json())
                    # Return the modified object using model_dump()
                    return collection_list.model_dump()
                except Exception as e:
                    logger.error(f"Failed to parse collections response: {e}")
                    return {"error": "Failed to parse collections response", "details": str(e)}
            else:
                return {"error": f"Failed to fetch collections: {response.status_code}", "details": response.text}
    except ValueError as e:
        return {"error": str(e)}


@mcp_server.tool
async def search_collection(
    collection_id: str,
    query: str,
    use_vector_index: bool = True,
    use_fulltext_index: bool = True,
    use_graph_index: bool = True,
    use_summary_index: bool = True,
    use_vision_index: bool = True,
    rerank: bool = True,
    topk: int = 5,
    query_keywords: list[str] = None,
    document_id: str | None = None,
    page_idx: int | None = None,
    context_offset: int = 0,
    image_asset_ids: list[str] | None = None,
) -> Dict[str, Any]:
    """Search for knowledge in a persistent collection/knowledge base using vector, full-text, graph, and/or summary search.

    PRIMARY USE CASE: This is the main tool for searching permanent knowledge repositories.
    Use this for general Q&A, knowledge retrieval, and accessing organized knowledge collections.

    For temporary files uploaded in a chat session, use search_chat_files instead.

    Args:
        collection_id: The ID of the collection to search in
        query: The search query
        query_keywords: The keywords extracted from query to use for fulltext search (optional), only effective when use_fulltext_index is True.
        use_vector_index: Whether to use vector/semantic search (default: True)
        use_fulltext_index: Whether to use full-text keyword search (default: True)
        use_graph_index: Whether to use knowledge graph search (default: True)
        use_summary_index: Whether to use summary search (default: True)
        use_vision_index: Whether to use vision search (default: True)
        rerank: Whether to enable reranking of search results for better relevance (default: True)
        topk: Maximum number of results to return per search type (default: 5)
        document_id: Set a document ID from a search hit to read original document context instead of running a search.
            Use this to verify cross-page continuations, full enumerations, and split sections before answering.
            With no page_idx, returns the original parsed text in document order (useful for DOCX and code).
        page_idx: Optional zero-based physical PDF page. In document context mode, returns that page and its immediate
            neighbors separately, with original page metadata. Neighboring pages may contain DIFFERENT FAQ entries;
            inspect the headings and continuation text rather than assigning them all to the matched FAQ.
        context_offset: Character offset in document context (default: 0). Each call returns at most 48000 characters.
            If context.truncated is true, continue with context.next_offset before claiming complete coverage.
        image_asset_ids: Optional list of at most six asset IDs already present in the document preview. Only in
            document context mode: explicitly request actual image-pixel inspection by the configured vision model.
            For PDF use page image asset IDs; for DOCX use the asset IDs in its markdown. Returns
            context.visual_observations. An asset link or OCR alone does not mean the image was visually inspected.

    Returns:
        Search results with relevant documents and metadata (SearchResult format)

    Note:
        Uses SearchResult view model for type-safe response parsing and validation.

        ```
        class SearchResultItem(BaseModel):
            rank: Optional[int] = Field(None, description='Result rank')
            score: Optional[float] = Field(None, description='Result score')
            content: Optional[str] = Field(None, description='Result content')
            source: Optional[str] = Field(None, description='Source document or metadata')
            recall_type: Optional[
                Literal['vector_search', 'graph_search', 'fulltext_search', 'summary_search']
            ] = Field(None, description='Recall type')
            metadata: Optional[dict[str, Any]] = Field(
                None, description='Metadata of the result'
            )


        class SearchResult(BaseModel):
            id: Optional[str] = Field(None, description='The id of the search result')
            query: Optional[str] = None
            vector_search: Optional[VectorSearchParams] = None
            fulltext_search: Optional[FulltextSearchParams] = None
            graph_search: Optional[GraphSearchParams] = None
            summary_search: Optional[SummarySearchParams] = None
            vision_search: Optional[VisionSearchParams] = None
            items: Optional[list[SearchResultItem]] = None
            created: Optional[datetime] = Field(
                None, description='The creation time of the search result'
            )
        ```

        The `result.items[x].metadata["page_idx"]` field indicates that the item's content is from page `page_idx` of the document (`metadata["source"]`). Note that `page_idx` is 0-indexed.

        Vector search results may include images. Images are indexed in two ways:
        1.  A multimodal embedding model converts the image into a vector. Since text and images share the same vector space, you can use text for semantic search.
        2.  A Vision LLM generates a text description of the image, which is then converted into a vector by a text embedding model. This also enables retrieval based on vector similarity.

        If `result.items[x].metadata["indexer"]` is "vision", the item is an image.
        - If `item.content` is empty, the image was retrieved via multimodal embedding.
        - If `item.content` is not empty, it contains a visual description of the image.

        Although the LLM's Tool message interface doesn't support direct image input (meaning you can't "see" the images, even as a vision model), you can use `item.content` to understand the image and answer questions.
        If you reference an image in your response, include its URL so the user can see it and understand your reasoning.

        If your final output is in Markdown, you can display the image using an image block, like `![](<asset_url>)`. Here's how to construct the `asset_url` in Python pseudo-code:

        ```python
        m = result.items[0].metadata
        if m.get("asset_id") and m.get("document_id") and m.get("collection_id") and m.get("mimetype"):
            asset_url = f"asset://{m['asset_id']}?document_id={m['document_id']}&collection_id={m['collection_id']}&mime_type={m['mimetype']}"
        ```

        The `asset_url` uses a special `asset://` scheme instead of `http/https`. This helps the front-end parse and handle it. It uses `asset_id` as the path and passes `document_id`, `collection_id`, and `mimetype` as query parameters. Note that `asset_id`, `document_id`, and `collection_id` are required to display the image and must not be omitted.
    """
    try:
        api_key = get_api_key()

        if document_id is not None:
            if not re.fullmatch(r"[A-Za-z0-9_-]+", collection_id) or not re.fullmatch(r"[A-Za-z0-9_-]+", document_id):
                return {"error": "Invalid collection or document ID"}
            if (page_idx is not None and page_idx < 0) or context_offset < 0:
                return {"error": "page_idx and context_offset must be non-negative"}
            return await _read_document_context(
                api_key, collection_id, document_id, query, page_idx, context_offset, image_asset_ids
            )
        if page_idx is not None or context_offset or image_asset_ids:
            return {"error": "document_id is required to read document context"}

        # Build search request based on enabled search types
        search_data = {"query": query, "rerank": rerank}

        # Add search configurations for enabled types
        if use_vector_index:
            search_data["vector_search"] = {"topk": topk, "similarity": 0.2}

        if use_fulltext_index:
            search_data["fulltext_search"] = {"topk": topk, "keywords": query_keywords}

        if use_graph_index:
            search_data["graph_search"] = {"topk": topk}

        if use_summary_index:
            search_data["summary_search"] = {"topk": topk, "similarity": 0.2}

        if use_vision_index:
            search_data["vision_search"] = {"topk": topk, "similarity": 0.2}

        # Ensure at least one search type is enabled
        if not any([use_vector_index, use_fulltext_index, use_graph_index, use_summary_index, use_vision_index]):
            return {"error": "At least one search type must be enabled"}

        # Use longer timeout for search operations (graph search can be time-consuming)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/collections/{collection_id}/searches",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=search_data,
            )
            if response.status_code == 200 or response.status_code == 201:
                try:
                    # Parse response using view model for type safety
                    search_result = SearchResult.model_validate(response.json())

                    _limit_search_results(search_result, topk)
                    _scope_search_sources(search_result, collection_id)

                    return search_result.model_dump()
                except Exception as e:
                    logger.error(f"Failed to parse search response: {e}")
                    return {"error": "Failed to parse search response", "details": str(e)}
            else:
                return {"error": f"Search failed: {response.status_code}", "details": response.text}
    except ValueError as e:
        return {"error": str(e)}


@mcp_server.tool
async def search_chat_files(
    chat_id: str,
    query: str,
    use_vector_index: bool = True,
    use_fulltext_index: bool = True,
    rerank: bool = True,
    topk: int = 5,
) -> Dict[str, Any]:
    """Search ONLY within files temporarily uploaded by the user in THIS specific chat session.

    IMPORTANT - When to Use This Tool:
    - ONLY when searching files that the user explicitly uploaded in THIS chat conversation
    - For temporary, session-specific document analysis (e.g., "analyze this PDF I just uploaded")
    - When the user references documents they shared in the current chat

    DO NOT Use This Tool For:
    - Searching general knowledge bases or collections (use search_collection instead)
    - Accessing persistent/permanent knowledge repositories
    - General Q&A that doesn't involve chat-uploaded files
    - When no files have been uploaded in the current chat

    Args:
        chat_id: The ID of the chat to search files in
        query: The search query
        use_vector_index: Whether to use vector/semantic search (default: True)
        use_fulltext_index: Whether to use full-text keyword search (default: True)
        rerank: Whether to enable reranking of search results for better relevance (default: True)
        topk: Maximum number of results to return per search type (default: 5)

    Returns:
        Search results with relevant documents and metadata (SearchResult format)

    Note:
        Uses SearchResult view model for type-safe response parsing and validation.

        SCOPE: This tool ONLY searches temporary files uploaded in the current chat.
        It does NOT search permanent knowledge collections.

        Return format follows the same structure as search_collection:
        - rank: Result rank
        - score: Result score
        - content: Result content
        - source: Source document or metadata
        - recall_type: Type of search that found this result
        - metadata: Additional metadata including page_idx, asset_id, etc.

        Images are handled the same way as in collection search:
        - metadata["indexer"] == "vision" indicates an image
        - Use asset:// URLs for displaying images in markdown
    """
    try:
        api_key = get_api_key()

        # Build search request based on enabled search types
        search_data = {"query": query, "rerank": rerank}

        # Add search configurations for enabled types
        if use_vector_index:
            search_data["vector_search"] = {"topk": topk, "similarity": 0.2}

        if use_fulltext_index:
            search_data["fulltext_search"] = {"topk": topk}

        # Ensure at least one search type is enabled
        if not any([use_vector_index, use_fulltext_index]):
            return {"error": "At least one search type must be enabled"}

        # Use longer timeout for search operations
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/chats/{chat_id}/search",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=search_data,
            )
            if response.status_code == 200 or response.status_code == 201:
                try:
                    # Parse response using view model for type safety
                    search_result = SearchResult.model_validate(response.json())

                    _limit_search_results(search_result, topk)

                    return search_result.model_dump()
                except Exception as e:
                    logger.error(f"Failed to parse chat search response: {e}")
                    return {"error": "Failed to parse chat search response", "details": str(e)}
            else:
                return {"error": f"Chat search failed: {response.status_code}", "details": response.text}
    except ValueError as e:
        return {"error": str(e)}


@mcp_server.tool
async def search_faq_by_chat_image(
    chat_id: str,
    file_id: str,
    collection_ids: list[str],
    topk: int = 3,
    similarity_threshold: float = 0.7,
) -> Dict[str, Any]:
    """Search FAQ-like knowledge base entries by an uploaded chat image.

    Args:
        chat_id: Chat ID that owns the uploaded image file.
        file_id: Uploaded chat file/document ID of the image.
        collection_ids: Collection IDs to search in.
        topk: Maximum number of matched FAQ/image results to return.
        similarity_threshold: Vision similarity threshold between 0 and 1.

    Returns:
        SearchResult-style payload with enriched FAQ text and metadata.

    Note:
        `file_id` should be the uploaded chat image document ID. For compatibility,
        this tool also accepts the message/file-style ID when it can be mapped back
        to the stored chat upload document in the same chat.
    """
    try:
        api_key = get_api_key()
        api_key_record = await async_db_ops.get_api_key_by_key(api_key)
        if not api_key_record:
            return {"error": "Unauthorized API key"}

        user_id = api_key_record.user
        if not chat_id or not file_id:
            return {"error": "chat_id and file_id are required"}
        if not collection_ids:
            return {"error": "collection_ids must contain at least one collection ID"}

        collections: list[Collection] = []
        for collection_id in collection_ids:
            collection = await async_db_ops.query_collection(user_id, collection_id)
            if not collection:
                continue
            collections.append(
                Collection(
                    id=collection.id,
                    title=collection.title,
                    description=collection.description,
                    type=collection.type,
                )
            )

        if not collections:
            return {"error": "No accessible collections found"}

        resolved_document_id = await _resolve_current_chat_image_document_id(user_id, chat_id, file_id)
        if not resolved_document_id:
            return {"error": "Image file not found or is not a valid uploaded chat image"}

        data_uri = await image_search_service._load_chat_image_as_data_uri(user_id, chat_id, resolved_document_id)
        if not data_uri:
            return {"error": "Image file not found or is not a valid uploaded chat image"}

        results = await image_search_service.search_similar_images(
            user_id=user_id,
            collections=collections,
            image_data_uri=data_uri,
            top_k=topk,
            similarity_threshold=similarity_threshold,
        )
        enriched_results = await image_search_service._enrich_results_with_faq_chunks(user_id, results)

        items = []
        for index, item in enumerate(enriched_results[:topk], start=1):
            metadata = item.metadata or {}
            items.append(
                SearchResultItem(
                    rank=index,
                    score=item.score,
                    content=item.text,
                    source=metadata.get("source") or metadata.get("name"),
                    recall_type="vision_search",
                    metadata=metadata,
                )
            )

        search_result = SearchResult(
            query=f"chat_image:{chat_id}/{resolved_document_id}",
            items=items,
            vision_search={"topk": topk, "similarity": similarity_threshold},
        )
        return search_result.model_dump()
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.exception("FAQ image search MCP tool failed")
        return {"error": "FAQ image search failed", "details": str(e)}


@mcp_server.tool
async def web_search(
    query: str = "",
    max_results: int = 5,
    timeout: int = 30,
    locale: str = "en-US",
    source: str = "",
    search_llms_txt: str = "",
) -> Dict[str, Any]:
    """Perform web search using various search engines with advanced domain targeting.

    Args:
        query: Search query for regular web search. Optional if only using LLM.txt discovery.
        max_results: Maximum number of results to return (default: 5)
        timeout: Request timeout in seconds (default: 30)
        locale: Browser locale (default: en-US)
        source: Optional domain or URL for site-specific filtering. When provided with query,
                limits search results to this domain (e.g., 'site:vercel.com query').
        search_llms_txt: Domain for LLM.txt discovery search. When provided, performs additional
                        LLM-optimized content discovery from the specified domain, independent
                        of the main search. Results are merged with regular search results.

    Returns:
        Web search results with URLs, titles, snippets, and metadata

    Note:
        Supports parallel execution of regular search and LLM.txt discovery.
        Results are automatically merged and ranked.
    """
    try:
        api_key = get_api_key()

        # Build search request
        search_data = {
            "max_results": max_results,
            "timeout": timeout,
            "locale": locale,
        }

        # Only include non-empty optional parameters
        if query and query.strip():
            search_data["query"] = query.strip()

        if source and source.strip():
            search_data["source"] = source.strip()

        if search_llms_txt and search_llms_txt.strip():
            search_data["search_llms_txt"] = search_llms_txt.strip()

        # Use longer timeout for web search operations
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/web/search",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=search_data,
            )
            if response.status_code == 200:
                try:
                    # Parse response using view model for type safety
                    search_response = WebSearchResponse.model_validate(response.json())
                    return search_response.model_dump()
                except Exception as e:
                    logger.error(f"Failed to parse web search response: {e}")
                    return {"error": "Failed to parse web search response", "details": str(e)}
            else:
                return {"error": f"Web search failed: {response.status_code}", "details": response.text}
    except ValueError as e:
        return {"error": str(e)}


@mcp_server.tool
async def search_sap_help(
    query: str,
    max_results: int = 5,
    timeout: int = 30,
    locale: str = "en-US",
) -> Dict[str, Any]:
    """Search only within help.sap.com using the web search pipeline.

    Args:
        query: Search query for SAP official help content.
        max_results: Maximum number of results to return.
        timeout: Request timeout in seconds.
        locale: Browser locale.

    Returns:
        Web search results restricted to help.sap.com.
    """
    try:
        api_key = get_api_key()
        if not query or not query.strip():
            return {"error": "query is required"}

        search_query = f"site:help.sap.com {query.strip()}"
        search_data = {
            "query": search_query,
            "max_results": max_results,
            "timeout": timeout,
            "locale": locale,
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/web/search",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=search_data,
            )
            if response.status_code != 200:
                return {"error": f"SAP Help search failed: {response.status_code}", "details": response.text}

            try:
                search_response = WebSearchResponse.model_validate(response.json())
            except Exception as e:
                logger.error(f"Failed to parse SAP Help search response: {e}")
                return {"error": "Failed to parse SAP Help search response", "details": str(e)}

            filtered_results = []
            for item in search_response.results:
                if item.domain and "help.sap.com" in item.domain.lower():
                    filtered_results.append(item)

            for index, item in enumerate(filtered_results, start=1):
                item.rank = index

            return WebSearchResponse(
                query=query.strip(),
                results=filtered_results,
                total_results=len(filtered_results),
                search_time=search_response.search_time,
            ).model_dump()
    except ValueError as e:
        return {"error": str(e)}


@mcp_server.tool
async def web_read(
    url_list: list[str],
    timeout: int = 30,
    locale: str = "en-US",
    max_concurrent: int = 5,
) -> Dict[str, Any]:
    """Read and extract content from web pages.

    Args:
        url_list: List of URLs to read content from (for single URL, use array with one element)
        timeout: Request timeout in seconds (default: 30)
        locale: Browser locale (default: en-US)
        max_concurrent: Maximum concurrent requests for multiple URLs (default: 5)

    Returns:
        Web content reading results with extracted text, titles, word counts, and metadata

    Note:
        Uses WebReadResponse view model for type-safe response parsing
    """
    try:
        api_key = get_api_key()

        # Validate url_list parameter
        if not url_list or len(url_list) == 0:
            return {"error": "url_list parameter is required and must contain at least one URL"}

        # Build read request using the correct WebReadRequest model
        read_data = {
            "url_list": url_list,
            "timeout": timeout,
            "locale": locale,
            "max_concurrent": max_concurrent,
        }

        # Use longer timeout for web content reading operations
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/web/read",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=read_data,
            )
            if response.status_code == 200:
                try:
                    # Parse response using view model for type safety
                    read_response = WebReadResponse.model_validate(response.json())
                    return read_response.model_dump()
                except Exception as e:
                    logger.error(f"Failed to parse web read response: {e}")
                    return {"error": "Failed to parse web read response", "details": str(e)}
            else:
                return {"error": f"Web read failed: {response.status_code}", "details": response.text}
    except ValueError as e:
        return {"error": str(e)}


# Add a resource for ApeRAG usage information
@mcp_server.resource("aperag://usage-guide")
async def aperag_usage_guide() -> str:
    """Resource providing usage guide for ApeRAG search."""
    return """
# ApeRAG Search Guide

ApeRAG provides powerful knowledge search capabilities across your collections.

## Available Operations:
1. **list_collections**: Get all available collections with essential information (ID, title, description)
2. **search_collection**: Search within collections using multiple search methods
3. **web_search**: Perform web search using various search engines (Google, DuckDuckGo, Bing)
4. **web_read**: Read and extract content from web pages

## Authentication:
API authentication is handled automatically through one of these methods:
1. **HTTP Authorization header**: `Authorization: Bearer your-api-key` (when using HTTP transport)
2. **Environment variable**: `APERAG_API_KEY=your-api-key` (fallback method)

The server will automatically try both methods in order of preference.

## Quick Start:
1. First, get available collections with essential information: `list_collections()`
2. Choose a collection from the list
3. Search the collection: `search_collection(collection_id="abc123", query="your question")`
   (By default, vector search, graph search, and reranking are enabled for optimal performance)

## Search Types:
You can enable/disable any combination of search methods:
- **Vector search** (use_vector_index): Semantic similarity search using embeddings (default: True)
- **Full-text search** (use_fulltext_index): Traditional keyword-based text search (default: True)
- **Graph search** (use_graph_index): Knowledge graph-based search (default: True)
- **Summary search** (use_summary_index): Search through document summaries (default: True)
- **Reranking** (rerank): AI-powered reranking for improved result relevance (default: True)

⚠️ **Important**: Full-text search can return large amounts of text content which may cause context window overflow with smaller LLM models. Use with caution and consider reducing topk when enabling fulltext search.

By default, vector search, full-text search, graph search, summary search, and reranking are enabled for comprehensive search coverage.

## Example Workflow:
```
# Step 1: Get collections with essential information
collections = list_collections()

# Step 2: Choose a collection from the list
# (collections.items contains collection ID, title, and description)
collection_id = collections.items[0].id

# Step 3: Search with default methods (vector + fulltext + graph + summary + rerank)
results = search_collection(
    collection_id=collection_id,
    query="How to deploy applications?",
    use_vector_index=True,
    use_fulltext_index=True,
    use_graph_index=True,
    use_summary_index=True,
    rerank=True,
    topk=5
)

# Or search with only specific methods
vector_only = search_collection(
    collection_id=collection_id,
    query="deployment strategies",
    use_vector_index=True,
    use_fulltext_index=False,
    use_graph_index=False,
    rerank=True,  # Rerank still enabled for better results
    topk=10
)

# Enable summary search for high-level document overviews
summary_search = search_collection(
    collection_id=collection_id,
    query="project overview",
    use_vector_index=True,
    use_fulltext_index=True,
    use_graph_index=True,
    use_summary_index=True,  # Enable summary search
    rerank=True,
    topk=5
)
```

Your search results will include relevant documents with context, similarity scores, and metadata.

## Web Search and Content Reading:
You can also search the web and extract content from web pages:

### Web Search Example:
```
# Basic web search
web_results = web_search(
    query="ApeRAG RAG system 2025",
    max_results=5,
    locale="zh-CN"
)

# Site-specific regular search
site_results = web_search(
    query="deployment documentation",
    source="vercel.com",  # limit search to vercel.com domain
    max_results=10
)

# LLM.txt discovery search (independent)
llms_txt_results = web_search(
    search_llms_txt="anthropic.com",  # discover LLM.txt content from anthropic.com
    max_results=5
)

# Combined search: regular + LLM.txt discovery
combined_results = web_search(
    query="machine learning tutorials",
    source="docs.python.org",  # regular search limited to Python docs
    search_llms_txt="openai.com",  # plus LLM.txt discovery from OpenAI
    max_results=8
)

# Search results include URLs, titles, snippets, and domains
for result in web_results.results:
    print(f"Title: {result.title}")
    print(f"URL: {result.url}")
    print(f"Snippet: {result.snippet}")
    print(f"Domain: {result.domain}")
```

### Web Content Reading Example:
```
# Read content from web pages (single URL - use array with one element)
content = web_read(
    url_list=["https://example.com/article"],  # single URL in array
    timeout=30
)

# Read from multiple URLs
content = web_read(
    url_list=["https://example.com/page1", "https://example.com/page2"],  # multiple URLs
    max_concurrent=2
)

# Content includes extracted text, titles, word counts
for result in content.results:
    if result.status == "success":
        print(f"Title: {result.title}")
        print(f"Content: {result.content}")
        print(f"Word Count: {result.word_count}")
```

### Combined Workflow Example:
```
# 1. Search web for recent information with LLM.txt discovery
web_results = web_search(
    query="latest AI developments 2025",
    source="anthropic.com",  # limit regular search to Anthropic's content
    search_llms_txt="anthropic.com",  # discover LLM-optimized content from Anthropic
    max_results=3
)

# 2. Extract URLs from search results
urls = [result.url for result in web_results.results]

# 3. Read full content from those pages
web_content = web_read(url_list=urls, max_concurrent=2)

# 4. Search your internal knowledge base for related information
collections = list_collections()
if collections.items:
    internal_results = search_collection(
        collection_id=collections.items[0].id,
        query="AI developments",
        rerank=True,  # Default rerank for better results
        topk=5
    )

# 5. Combine results for comprehensive analysis
print("=== Web Results ===")
for result in web_results.results:
    print(f"[{result.domain}] {result.title}: {result.url}")

print("\n=== Web Content ===")
for content in web_content.results:
    if content.status == "success":
        print(f"📄 {content.title} ({content.word_count} words)")

print("\n=== Internal Knowledge ===")
for item in internal_results.items:
    print(f"🔍 {item.content[:100]}...")

# Now you have both web and internal knowledge base results!
```
"""


# Add a prompt for search assistance
@mcp_server.prompt
async def search_assistant() -> str:
    """Help prompt for effective ApeRAG searching."""
    return """
# ApeRAG Search Assistant

I can help you search your knowledge base effectively using ApeRAG.

## How to use me:
1. **Tell me what you're looking for** - I'll help you search across your collections
2. **Ask specific questions** - I can find relevant documents and provide context
3. **Explore collections** - I can show you what collections are available

## What I can do:
- 🔍 **Search your knowledge base** using multiple search methods
- 📚 **Browse your collections** to understand what data you have (with essential details)
- 🎯 **Find specific information** with precise queries
- 💡 **Suggest search strategies** for complex queries
- 🌐 **Search the web** for latest information using multiple search engines
- 📄 **Read web content** and extract clean text from any web page
- 🔗 **Combine web and internal search** for comprehensive results
- 🤖 **LLM.txt discovery** for AI-optimized content from any domain
- 🎯 **Domain-targeted search** with flexible result filtering
- 🏢 **Site-specific search** to focus on specific websites or domains

## Search Tips:
- Use **specific terms** for better results
- **Combine different search methods** by enabling/disabling vector, fulltext, and graph indexes
- **Combine keywords** with natural language questions
- **Adjust topk values** based on your needs (number of results per search type)
- Enable **all search types** for comprehensive results, or **specific types** for focused searches

## Authentication:
API authentication is handled automatically through:
1. **HTTP Authorization header**: `Authorization: Bearer your-api-key` (preferred for HTTP transport)
2. **Environment variable**: `APERAG_API_KEY=your-api-key` (fallback method)

Make sure at least one authentication method is properly configured in your MCP client.

Ready to help you find the information you need!
"""


def get_api_key() -> str:
    """Get API key from HTTP headers or environment variable.

    Priority order:
    1. Authorization header from HTTP request (using FastMCP dependency)
    2. APERAG_API_KEY environment variable

    Returns:
        API key string

    Raises:
        ValueError: If API key is not found
    """
    # Try to get API key from HTTP headers first
    try:
        # Use FastMCP's dependency function to get HTTP headers
        headers = get_http_headers()

        if headers:
            # Try to extract Authorization header
            auth_header = headers.get("Authorization") or headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                api_key = auth_header[7:]  # Remove 'Bearer ' prefix
                logger.info(f"API key found in Authorization header, length: {len(api_key)}")
                return api_key

    except Exception as e:
        # get_http_headers() might fail if not in HTTP request context
        logger.debug(f"Could not extract API key from headers: {e}")

    # Fallback to environment variable
    api_key = os.getenv("APERAG_API_KEY")

    if api_key:
        logger.info(f"API key found in environment variable, length: {len(api_key)}")
        return api_key

    raise ValueError(
        "API key not found. Please provide API key via:\n"
        "1. Authorization: Bearer <token> HTTP header, or\n"
        "2. APERAG_API_KEY environment variable"
    )


# Export the server instance
__all__ = ["mcp_server"]
