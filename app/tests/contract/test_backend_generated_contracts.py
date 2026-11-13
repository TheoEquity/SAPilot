"""Exercise the HTTP contracts used by the generated frontend client."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aperag.db.models import Role
from aperag.schema import view_models
from aperag.views import collections, main, marketplace_collections, prompts, quota, settings


def _client(router, dependency):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[dependency] = lambda: SimpleNamespace(id="user-1", role=Role.ADMIN)
    return TestClient(app), app.openapi()


def test_provider_model_writes_require_and_forward_json_bodies(monkeypatch):
    provider_model = {
        "provider_name": "provider-1",
        "api": "completion",
        "model": "model-1",
        "custom_llm_provider": "openai",
        "context_window": None,
        "max_input_tokens": None,
        "max_output_tokens": None,
        "tags": [],
        "created": None,
        "updated": None,
    }
    create = AsyncMock(return_value=provider_model)
    update = AsyncMock(return_value=provider_model)
    monkeypatch.setattr(main, "create_llm_provider_model", create)
    monkeypatch.setattr(main, "update_llm_provider_model", update)
    monkeypatch.setattr("aperag.utils.audit_decorator._log_audit_async", AsyncMock())
    client, spec = _client(main.router, main.required_user)
    create_path = "/api/v1/llm_providers/{provider_name}/models"
    update_path = "/api/v1/llm_providers/{provider_name}/models/{api}/{model}"

    assert spec["paths"][create_path]["post"]["requestBody"]["required"] is True
    assert spec["paths"][update_path]["put"]["requestBody"]["required"] is True
    assert client.post("/api/v1/llm_providers/provider-1/models").status_code == 422
    assert client.put("/api/v1/llm_providers/provider-1/models/completion/model-1").status_code == 422
    create.assert_not_awaited()
    update.assert_not_awaited()

    created = client.post(
        "/api/v1/llm_providers/provider-1/models",
        json={"provider_name": "provider-1", "api": "completion", "model": "model-1", "custom_llm_provider": "openai"},
    )
    assert created.status_code == 200
    assert created.json() == provider_model
    create.assert_awaited_once_with(
        "provider-1",
        {"provider_name": "provider-1", "api": "completion", "model": "model-1", "custom_llm_provider": "openai",
         "context_window": None, "max_input_tokens": None, "max_output_tokens": None, "tags": []},
        "user-1", True,
    )

    updated = client.put(
        "/api/v1/llm_providers/provider-1/models/completion/model%2Fone",
        json={"max_output_tokens": 100},
    )
    assert updated.status_code == 200
    assert updated.json() == provider_model
    update.assert_awaited_once_with(
        "provider-1", "completion", "model/one",
        {"custom_llm_provider": None, "context_window": None, "max_input_tokens": None,
         "max_output_tokens": 100, "tags": None},
        "user-1", True,
    )


def test_provider_response_keeps_omitted_api_key_omitted(monkeypatch):
    provider = {
        "name": "provider-1", "user_id": "user-1", "label": "Provider", "completion_dialect": "openai",
        "embedding_dialect": "openai", "rerank_dialect": "jina_ai", "allow_custom_base_url": False,
        "base_url": "https://example.invalid/v1", "extra": None, "created": None, "updated": None,
    }
    monkeypatch.setattr(main, "get_llm_provider", AsyncMock(return_value=provider))
    monkeypatch.setattr(main, "get_llm_configuration", AsyncMock(return_value={"providers": [provider], "models": []}))
    monkeypatch.setattr(main, "create_llm_provider", AsyncMock(return_value=provider))
    monkeypatch.setattr(main, "update_llm_provider", AsyncMock(return_value=provider))
    monkeypatch.setattr(main, "publish_llm_provider", AsyncMock(return_value=provider))
    monkeypatch.setattr("aperag.utils.audit_decorator._log_audit_async", AsyncMock())
    client, _ = _client(main.router, main.required_user)
    provider_responses = [
        client.get("/api/v1/llm_providers/provider-1"),
        client.post("/api/v1/llm_providers", json={"label": "Provider", "base_url": provider["base_url"]}),
        client.put("/api/v1/llm_providers/provider-1", json={"label": "Provider"}),
        client.post("/api/v1/llm_providers/provider-1/publish"),
    ]
    for response in provider_responses:
        assert response.status_code == 200
        assert response.json() == provider
    configuration = client.get("/api/v1/llm_configuration")
    assert configuration.status_code == 200
    assert configuration.json() == {"providers": [provider], "models": []}


def test_document_preview_and_graph_preserve_service_fields(monkeypatch):
    from aperag.service.graph_service import graph_service

    preview = view_models.DocumentPreview(
        doc_object_path="original.pdf", doc_filename="original.pdf", converted_pdf_object_path=None,
        markdown_content="text", chunks=[], vision_chunks=[],
    )
    graph = {
        "nodes": [{"id": "node-1", "labels": ["Company"],
                   "properties": {"entity_id": "node-1", "entity_name": "Company One"}}],
        "edges": [{"id": "edge-1", "type": "DIRECTED", "source": "node-1", "target": "node-1",
                   "properties": {"weight": 0.5, "custom": "retained"}}],
        "is_truncated": False,
    }
    monkeypatch.setattr(collections.document_service, "get_document_preview", AsyncMock(return_value=preview))
    monkeypatch.setattr(graph_service, "get_knowledge_graph", AsyncMock(return_value=graph))
    client, _ = _client(collections.router, collections.required_user)
    preview_response = client.get("/api/v1/collections/collection-1/documents/document-1/preview")
    graph_response = client.get("/api/v1/collections/collection-1/graphs")
    assert preview_response.status_code == 200
    assert preview_response.json() == preview.model_dump(mode="json")
    assert graph_response.status_code == 200
    assert graph_response.json() == graph


def test_marketplace_preview_and_graph_preserve_service_fields(monkeypatch):
    from aperag.service.graph_service import graph_service

    monkeypatch.setattr(
        marketplace_collections.marketplace_collection_service, "_check_marketplace_access",
        AsyncMock(return_value={"owner_user_id": "owner-1"}),
    )
    preview = view_models.DocumentPreview(doc_filename="shared.pdf")
    graph = {"nodes": [], "edges": [], "is_truncated": False}
    monkeypatch.setattr(marketplace_collections.document_service, "get_document_preview", AsyncMock(return_value=preview))
    monkeypatch.setattr(graph_service, "get_knowledge_graph", AsyncMock(return_value=graph))
    client, _ = _client(marketplace_collections.router, marketplace_collections.optional_user)
    preview_response = client.get("/api/v1/marketplace/collections/collection-1/documents/document-1/preview")
    graph_response = client.get("/api/v1/marketplace/collections/collection-1/graph")
    assert preview_response.status_code == 200
    assert preview_response.json() == preview.model_dump(mode="json")
    assert graph_response.status_code == 200
    assert graph_response.json() == graph


def test_settings_mineru_token_response_and_missing_token_status(monkeypatch):
    get_setting = AsyncMock(return_value=None)
    test_token = AsyncMock(side_effect=[
        {"status_code": 401, "data": {"msg": "invalid token"}},
        {"status_code": 500, "data": ["upstream unavailable"]},
    ])
    monkeypatch.setattr(settings.setting_service, "get_setting", get_setting)
    monkeypatch.setattr(settings.setting_service, "test_mineru_token", test_token)
    client, spec = _client(settings.router, settings.required_user)
    operation = spec["paths"]["/api/v1/settings/test_mineru_token"]["post"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/MineruTokenTestResponse"
    )
    assert operation["responses"]["404"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/MineruTokenMissingResponse"
    )

    missing = client.post("/api/v1/settings/test_mineru_token")
    assert missing.status_code == 404
    assert missing.json() == {"code": -1, "msg": "MinerU API token not set"}
    test_token.assert_not_awaited()

    invalid = client.post("/api/v1/settings/test_mineru_token", json={"token": "invalid"})
    upstream_failure = client.post("/api/v1/settings/test_mineru_token", json={"token": "unavailable"})
    assert invalid.status_code == upstream_failure.status_code == 200
    assert invalid.json() == {"status_code": 401, "data": {"msg": "invalid token"}}
    assert upstream_failure.json() == {"status_code": 500, "data": ["upstream unavailable"]}


def test_quota_recalculation_response_preserves_usage_and_auth_error(monkeypatch):
    recalculate = AsyncMock(return_value={"max_collection_count": 2, "max_document_count": 3, "max_bot_count": 1})
    monkeypatch.setattr(quota.quota_service, "recalculate_user_usage", recalculate)
    client, spec = _client(quota.router, quota.required_user)
    operation = spec["paths"]["/api/v1/quotas/{user_id}/recalculate"]["post"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/QuotaRecalculateResponse"
    )
    response = client.post("/api/v1/quotas/user-2/recalculate")
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Quota usage recalculated successfully",
        "updated_usage": {"max_collection_count": 2, "max_document_count": 3, "max_bot_count": 1},
    }
    recalculate.assert_awaited_once_with("user-2")

    client.app.dependency_overrides[quota.required_user] = lambda: SimpleNamespace(id="user-3", role=Role.RO)
    denied = client.post("/api/v1/quotas/user-2/recalculate")
    assert denied.status_code == 500  # Existing broad exception handler converts the admin guard's 403.
    recalculate.assert_awaited_once()


def test_rebuild_failed_indexes_response_covers_both_service_variants(monkeypatch):
    rebuild = AsyncMock(side_effect=[
        {"code": "200", "message": "No failed indexes found to rebuild", "affected_documents": 0},
        {"code": "200", "message": "Failed indexes rebuild initiated for 2 documents", "affected_documents": 2},
    ])
    monkeypatch.setattr(collections.document_service, "rebuild_failed_indexes", rebuild)
    monkeypatch.setattr("aperag.utils.audit_decorator._log_audit_async", AsyncMock())
    client, spec = _client(collections.router, collections.required_user)
    operation = spec["paths"]["/api/v1/collections/{collection_id}/rebuild_failed_indexes"]["post"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/RebuildFailedIndexesResponse"
    )
    empty = client.post("/api/v1/collections/collection-1/rebuild_failed_indexes")
    rebuilt = client.post("/api/v1/collections/collection-1/rebuild_failed_indexes")
    assert empty.status_code == rebuilt.status_code == 200
    assert empty.json() == {"code": "200", "message": "No failed indexes found to rebuild", "affected_documents": 0}
    assert rebuilt.json() == {
        "code": "200", "message": "Failed indexes rebuild initiated for 2 documents", "affected_documents": 2,
    }


def test_user_prompts_response_keeps_all_details_and_openapi_schema(monkeypatch):
    prompt_data = {
        "agent_system": {"content": "system text", "source": "user", "customized": True, "description": "personal"},
        "agent_query": {"content": "query text", "source": "system", "customized": False, "description": "default"},
        "index_graph": {"content": "graph text", "source": "hardcoded", "customized": False, "description": None},
        "index_summary": {"content": "summary text", "source": "hardcoded", "customized": False, "description": None},
        "index_vision": {"content": "vision text", "source": "hardcoded", "customized": False, "description": None},
    }
    service_call = AsyncMock(return_value=prompt_data)
    monkeypatch.setattr(prompts.prompt_template_service, "get_user_prompts", service_call)
    client, spec = _client(prompts.router, prompts.required_user)
    operation = spec["paths"]["/api/v1/prompts/user"]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/UserPromptsResponse"
    )
    assert spec["components"]["schemas"]["UserPromptsResponse"]["properties"]["agent_system"]["anyOf"][0][
        "$ref"
    ].endswith("/PromptDetail")
    response = client.get("/api/v1/prompts/user")
    assert response.status_code == 200
    assert response.json() == prompt_data
    service_call.assert_awaited_once_with(user_id="user-1")
