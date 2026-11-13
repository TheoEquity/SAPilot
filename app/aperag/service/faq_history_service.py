"""Find FAQ turns and validate the sources behind a saved answer."""

import logging
import re
from datetime import datetime
from typing import Any, Iterator
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import select, tuple_

from aperag.chat.history.message import StoredChatMessage
from aperag.db.models import Collection, CollectionStatus, Document, DocumentIndex, DocumentIndexStatus, DocumentStatus
from aperag.db.ops import AsyncDatabaseOps
from aperag.objectstore.base import get_async_object_store

logger = logging.getLogger(__name__)

_REFRESH = re.compile(
    r"\s*(?:请\s*)?(?:按最新资料\s*)?(?:帮我\s*)?(?:重新(?:查(?:询|一下)?|检索)|再查一次)(?:[：:]\s*(.+)|[。！!？?]*)\s*",
    re.DOTALL,
)
_CORRECTION = re.compile(
    r"\s*(?:这条|这份|这个|刚才那条)\s*FAQ\s*(?:不对|不匹配|不适用|错了)"
    r"(?:[，,。；;：:！!]\s*(.*))?\s*",
    re.IGNORECASE | re.DOTALL,
)
_ASSET_LINK = re.compile(r"!?\[[^\]\n]*\]\((asset://[^\s)]+)\)")


def faq_refresh_request(query: str) -> tuple[bool, str]:
    match = _REFRESH.fullmatch(query)
    return (True, (match[1] or "").strip()) if match else (False, "")


def faq_correction_request(query: str) -> str | None:
    match = _CORRECTION.fullmatch(query)
    return (match[1] or "").strip() if match else None


def history_turns(
    messages: list[StoredChatMessage], chat_id: str
) -> Iterator[tuple[StoredChatMessage, StoredChatMessage]]:
    questions = {
        message.message_id: message
        for message in messages
        if message.chat_id == chat_id and message.message_id and message.role == "human"
    }
    for answer in reversed(messages):
        if answer.chat_id == chat_id and answer.role == "ai" and answer.message_id in questions:
            yield questions[answer.message_id], answer


def saved_faq(answer: StoredChatMessage) -> dict[str, Any]:
    for part in answer.parts:
        if part.type == "message":
            return (part.metadata or {}).get("faq") or {}
    return {}


def faq_reference_key(reference: dict[str, Any]) -> tuple[str, str, str]:
    metadata = reference.get("metadata") or {}
    return (
        metadata.get("collection_id") or "",
        metadata.get("document_id") or "",
        metadata.get("faq_id") or metadata.get("evidence_id") or metadata.get("chunk_id") or "",
    )


def is_rejected_faq_reference(
    reference: dict[str, Any],
    rejected: set[tuple[str, str, str]],
) -> bool:
    collection, document, entry = faq_reference_key(reference)
    if (reference.get("metadata") or {}).get("faq_id"):
        return (collection, document, entry) in rejected or (collection, document, "") in rejected
    # A passage without a FAQ ID cannot establish that it is a different entry in the same document.
    return any((collection, document) == source[:2] for source in rejected)


def faq_rejections(turns: list[tuple[StoredChatMessage, StoredChatMessage]], query: str) -> set[tuple[str, str, str]]:
    rejected = set()
    for _, answer in turns:
        faq = saved_faq(answer)
        correction = faq.get("correction")
        if correction and query in {correction.get("query"), faq.get("query")}:
            rejected.update(tuple(source) for source in correction.get("sources", []))
    return rejected


def _accessible_documents(user: str, sources: set[tuple[str, str]]):
    return (
        select(Document)
        .join(Collection, Collection.id == Document.collection_id)
        .where(
            tuple_(Document.collection_id, Document.id).in_(sources),
            Collection.user == user,
            Collection.status == CollectionStatus.ACTIVE,
            Collection.gmt_deleted.is_(None),
            Document.user == user,
            Document.status == DocumentStatus.COMPLETE,
            Document.gmt_deleted.is_(None),
        )
    )


def _source(reference: dict[str, Any]) -> tuple[str, str]:
    metadata = reference.get("metadata") or {}
    return metadata.get("collection_id"), metadata.get("document_id")


async def accessible_faq_references(
    db: AsyncDatabaseOps,
    user: str,
    references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not references:
        return []

    async def load_sources(session):
        result = await session.execute(_accessible_documents(user, {_source(ref) for ref in references}))
        return {(doc.collection_id, doc.id) for doc in result.scalars()}

    sources = await db._execute_query(load_sources)
    return [ref for ref in references if _source(ref) in sources]


async def faq_source_versions(
    db: AsyncDatabaseOps,
    user: str,
    collection_ids: set[str],
    content: str,
    references: list[dict[str, Any]],
    *,
    started_at: datetime | None = None,
) -> dict[str, Any] | None:
    """Use current document/index metadata and object existence, without running retrieval."""
    sources = set()
    assets = set()
    for reference in references:
        metadata = reference.get("metadata") or {}
        collection, document = _source(reference)
        if collection not in collection_ids or not document:
            return None
        sources.add((collection, document))
        if metadata.get("asset_id"):
            assets.add((collection, document, metadata["asset_id"]))
    if not sources or not any((ref.get("metadata") or {}).get("grounded") is True for ref in references):
        return None

    for text in [content, *(reference.get("text") or "" for reference in references)]:
        for url in _ASSET_LINK.findall(text):
            try:
                parsed = urlsplit(url)
            except ValueError:
                return None
            params = parse_qs(parsed.query)
            collections, documents = params.get("collection_id", []), params.get("document_id", [])
            if len(collections) != 1 or len(documents) != 1 or (collections[0], documents[0]) not in sources:
                return None
            assets.add((collections[0], documents[0], parsed.netloc))

    async def load_sources(session):
        result = await session.execute(
            _accessible_documents(user, sources)
            .add_columns(DocumentIndex)
            .join(DocumentIndex, DocumentIndex.document_id == Document.id)
            .order_by(Document.id, DocumentIndex.index_type)
        )
        return result.all()

    try:
        versions = {}
        paths = {}
        for document, index in await db._execute_query(load_sources):
            if index.status != DocumentIndexStatus.ACTIVE or index.version != index.observed_version:
                return None
            if started_at and max(document.gmt_updated, index.gmt_updated) > started_at:
                return None
            paths[document.collection_id, document.id] = document.object_store_base_path()
            version = versions.setdefault(
                document.id,
                {
                    "collection_id": document.collection_id,
                    "name": document.name,
                    "hash": document.content_hash,
                    "updated": document.gmt_updated.isoformat(),
                    "indexes": {},
                },
            )
            version["indexes"][str(index.index_type)] = [index.id, index.version, index.gmt_updated.isoformat()]
        if paths.keys() != sources:
            return None

        if assets:
            store = get_async_object_store()
            for collection, document, asset in assets:
                if not re.fullmatch(r"[\w.-]+", asset, re.ASCII) or asset in {".", ".."}:
                    return None
                if not await store.get_obj_size(f"{paths[collection, document]}/assets/{asset}"):
                    return None
        return versions
    except Exception:
        logger.warning("chat.faq.source_validation_failed", exc_info=True)
        return None
