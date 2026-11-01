import json
from types import SimpleNamespace

import pytest
from llama_index.core.schema import NodeRelationship
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

from aperag.docparser.base import AssetBinPart
from aperag.index.vision_index import VisionIndexer


@pytest.mark.parametrize(
    "multimodal,vision_completion,expected_methods",
    [
        (True, False, ["multimodal_embedding"]),
        (False, True, ["vision_to_text"]),
        (True, True, ["multimodal_embedding", "vision_to_text"]),
    ],
)
def test_vision_nodes_preserve_source_document_through_real_qdrant_serialization(
    monkeypatch, multimodal, vision_completion, expected_methods
):
    document_id = "document-authorized"
    collection_id = "collection-authorized"
    client = QdrantClient(":memory:")
    store = QdrantVectorStore(client=client, collection_name="vision_identity")
    embedding = SimpleNamespace(
        is_multimodal=lambda: multimodal,
        embed_documents=lambda inputs: [[1.0, 0.0] for _ in inputs],
    )
    completion = SimpleNamespace(is_vision_model=lambda: vision_completion, generate=lambda **kwargs: "Visible SAP field")
    monkeypatch.setattr(
        "aperag.index.vision_index.get_collection_embedding_service_sync", lambda collection: (embedding, 2)
    )
    monkeypatch.setattr("aperag.index.vision_index.get_collection_completion_service_sync", lambda collection: completion)
    monkeypatch.setattr(
        "aperag.index.vision_index.get_vector_db_connector",
        lambda **kwargs: SimpleNamespace(connector=SimpleNamespace(store=store)),
    )
    indexer = VisionIndexer()
    monkeypatch.setattr(indexer, "is_enabled", lambda collection: True)
    part = AssetBinPart(
        asset_id="page_0.png", data=b"actual-image-bytes", mime_type="image/png",
        metadata={"doc_id": document_id, "page_idx": 0, "name": "source.pdf"},
    )
    try:
        result = indexer.create_index(document_id, "source", [part], SimpleNamespace(id=collection_id))
        assert result.success is True
        points, _ = client.scroll(collection_name="vision_identity", limit=10, with_payload=True)
        assert len(points) == len(expected_methods)
        assert {p.payload["index_method"] for p in points} == set(expected_methods)
        for point in points:
            payload = point.payload
            assert payload["doc_id"] == document_id
            assert payload["document_id"] == document_id
            assert payload["ref_doc_id"] == document_id
            assert payload["collection_id"] == collection_id
            assert payload["asset_id"] == "page_0.png"
            node = json.loads(payload["_node_content"])
            assert node["relationships"][NodeRelationship.SOURCE.value]["node_id"] == document_id
            assert node["metadata"]["document_id"] == document_id
        # Standard document-scoped Qdrant filters must select the written vision nodes.
        for identity_key in ("doc_id", "document_id", "ref_doc_id"):
            filtered, _ = client.scroll(
                collection_name="vision_identity", limit=10,
                scroll_filter=models.Filter(must=[models.FieldCondition(key=identity_key, match=models.MatchValue(value=document_id))]),
            )
            assert {p.id for p in filtered} == set(result.data["context_ids"])
        assert part.metadata == {"doc_id": document_id, "page_idx": 0, "name": "source.pdf"}
    finally:
        client.close()
