import asyncio
import base64
import io
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from aperag.db.models import DocumentStatus
from aperag.query.query import DocumentWithScore
from aperag.schema import view_models
from aperag.service.image_search_service import ImageSearchService


def chat_document(**overrides):
    fields = {
        "user": "user-a",
        "name": "upload.png",
        "object_path": "uploads/image-a",
        "doc_metadata": json.dumps({"file_type": "chat_upload", "chat_id": "chat-a"}),
        "status": DocumentStatus.COMPLETE,
        "gmt_deleted": None,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


@pytest.mark.parametrize(
    "document",
    [
        chat_document(user="user-b"),
        chat_document(doc_metadata='{"file_type":"chat_upload","chat_id":"chat-b"}'),
        chat_document(doc_metadata='{"file_type":"knowledge","chat_id":"chat-a"}'),
        chat_document(doc_metadata="invalid-json"),
        chat_document(name="upload.pdf"),
        chat_document(status=DocumentStatus.DELETED),
        chat_document(gmt_deleted=datetime(2026, 1, 1, tzinfo=timezone.utc)),
    ],
)
def test_chat_image_load_rejects_foreign_or_non_image_attachments(monkeypatch, document):
    service = ImageSearchService()
    service.db_ops = SimpleNamespace(query_document_by_id=AsyncMock(return_value=document))
    monkeypatch.setattr(
        "aperag.service.image_search_service.get_object_store",
        lambda: pytest.fail("Rejected attachments must not be read from storage"),
    )

    assert asyncio.run(service._load_chat_image_as_data_uri("user-a", "chat-a", "doc-a")) == ""


def test_chat_image_load_preserves_png_bytes_and_supports_metadata_object_path(monkeypatch):
    content = b"\x89PNG\r\n\x1a\nexact-original-payload"
    document = chat_document(
        object_path=None,
        doc_metadata=json.dumps(
            {"file_type": "chat_upload", "chat_id": "chat-a", "object_path": "uploads/image-a"}
        ),
    )
    service = ImageSearchService()
    service.db_ops = SimpleNamespace(query_document_by_id=AsyncMock(return_value=document))
    monkeypatch.setattr(
        "aperag.service.image_search_service.get_object_store",
        lambda: SimpleNamespace(get=lambda path: io.BytesIO(content) if path == "uploads/image-a" else None),
    )

    uri = asyncio.run(service._load_chat_image_as_data_uri("user-a", "chat-a", "doc-a"))

    assert uri.startswith("data:image/png;base64,")
    assert base64.b64decode(uri.partition(",")[2]) == content


def test_inaccessible_collection_cannot_trigger_image_embedding(monkeypatch):
    service = ImageSearchService()
    service.db_ops = SimpleNamespace(query_collection=AsyncMock(return_value=None))
    monkeypatch.setattr(
        "aperag.service.image_search_service.get_collection_embedding_service_sync",
        lambda collection: pytest.fail("Inaccessible collections must not invoke a model"),
    )

    results = asyncio.run(
        service.search_similar_images(
            "user-a", [view_models.Collection(id="collection-b", title="Foreign")], "data:image/png;base64,eA==", 3, 0.7
        )
    )

    assert results == []


def test_chat_image_search_context_includes_every_uploaded_image(monkeypatch):
    service = ImageSearchService()
    service._load_chat_image_as_data_uri = AsyncMock(side_effect=lambda user, chat, doc: f"data:image/png;base64,{doc}")

    async def search(**kwargs):
        image = kwargs["image_data_uri"].rsplit(",", 1)[1]
        return [
            DocumentWithScore(
                text=f"Evidence for {image}",
                score=0.9,
                metadata={"collection_id": "collection-a", "document_id": image, "asset_id": f"{image}.png"},
            )
        ]

    service.search_similar_images = search
    service._enrich_results_with_faq_chunks = AsyncMock(side_effect=lambda user, results: results)

    context = asyncio.run(
        service.build_chat_image_search_context(
            "user-a",
            "chat-a",
            [view_models.File(id="first"), view_models.File(id="second")],
            [view_models.Collection(id="collection-a", title="Knowledge")],
            top_k=5,
        )
    )

    assert "Evidence for first" in context
    assert "Evidence for second" in context
