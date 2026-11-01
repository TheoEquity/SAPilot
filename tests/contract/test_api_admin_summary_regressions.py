"""Execute affected Python handlers with real schemas and isolated IO."""

import ast
import asyncio
import logging
import sys
import time
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from aperag.schema import view_models
from aperag.schema.utils import parseCollectionConfig

ROOT = Path(__file__).resolve().parents[2]


def load_def(path, name, namespace):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    node = next(n for n in tree.body if getattr(n, "name", None) == name)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        node.decorator_list = []
        node.returns = None
        for arg in node.args.args + node.args.kwonlyargs:
            arg.annotation = None
        for arg in node.args.args:
            arg.annotation = None
        node.args.defaults = []
        node.args.kw_defaults = [None] * len(node.args.kwonlyargs)
    module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(module, str(ROOT / path), "exec"), namespace)
    return namespace[name]


def test_audit_response_accepts_every_persisted_resource_type():
    resource = load_def("aperag/db/models.py", "AuditResource", {"Enum": Enum})
    for item in resource:
        assert view_models.AuditLog(resource_type=item.value).resource_type == item.value


@pytest.mark.parametrize("target_role,own,admin_count,status", [
    ("ro", False, 1, None), ("admin", False, 1, 400),
    ("admin", True, 2, 400), ("ro", False, 1, 404),
])
def test_delete_user_uses_request_transaction_and_retains_guards(target_role, own, admin_count, status):
    target = SimpleNamespace(id="admin" if own else "test-user", role=target_role)
    session = SimpleNamespace(execute=AsyncMock(return_value=Mock()), commit=AsyncMock())
    session.execute.return_value.scalars.return_value.first.return_value = None if status == 404 else target
    repository = SimpleNamespace(delete_user=AsyncMock())
    factory = Mock(return_value=repository)
    async def delete_user(user):
        raise AssertionError("Deletion must use the request session")

    fn = load_def("aperag/views/auth.py", "delete_user_view", {
        "User": SimpleNamespace(id=Mock()), "Role": SimpleNamespace(ADMIN="admin"),
        "async_db_ops": SimpleNamespace(query_admin_count=AsyncMock(return_value=admin_count), delete_user=delete_user),
        "AsyncDatabaseOps": factory, "HTTPException": HTTPException,
    })
    # The handler imports sqlalchemy.select: only its query expression is replaced.
    from unittest.mock import patch
    with patch.dict(sys.modules, {"sqlalchemy": SimpleNamespace(select=Mock(return_value=Mock()))}):
        if status:
            with pytest.raises(HTTPException) as exc:
                asyncio.run(fn(None, target.id, session, SimpleNamespace(id="admin")))
            assert exc.value.status_code == status
            repository.delete_user.assert_not_awaited()
            session.commit.assert_not_awaited()
        else:
            asyncio.run(fn(None, target.id, session, SimpleNamespace(id="admin")))
            factory.assert_called_once_with(session)
            repository.delete_user.assert_awaited_once_with(target)
            session.commit.assert_awaited_once()


@pytest.mark.parametrize("typed_config", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
def test_summary_trigger_handles_database_and_api_collections(typed_config, enabled):
    session = SimpleNamespace(add=Mock(), commit=AsyncMock())

    async def sessions():
        yield session

    tree = ast.parse((ROOT / "aperag/service/collection_summary_service.py").read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "CollectionSummaryService")
    method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "trigger_collection_summary_generation")
    method.returns = None
    for arg in method.args.args:
        arg.annotation = None
    namespace = {
        "get_async_session": sessions, "parseCollectionConfig": parseCollectionConfig,
        "view_models": view_models, "CollectionConfig": view_models.CollectionConfig,
        "CollectionSummary": lambda **kw: SimpleNamespace(**kw),
        "CollectionSummaryStatus": SimpleNamespace(PENDING="PENDING", GENERATING="GENERATING"),
        "logger": logging.getLogger(__name__),
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), "summary", "exec"), namespace)
    service = SimpleNamespace(_get_summary_by_collection_id=AsyncMock(return_value=None))
    config = view_models.CollectionConfig(enable_summary=enabled)
    collection = SimpleNamespace(id="test-collection", config=config if typed_config else config.model_dump_json())
    assert asyncio.run(namespace[method.name](service, collection)) is enabled
    assert session.add.call_count == int(enabled)
    assert session.commit.await_count == int(enabled)


def test_unimplemented_compatibility_endpoint_returns_501():
    tree = ast.parse((ROOT / "aperag/views/openai.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef))
    # Exercise the actual router decorator/status without loading auth or DB IO.
    from fastapi import APIRouter, Depends, Request
    formatter = load_def("aperag/service/chat_completion_service.py", "OpenAIFormatter", {
        "time": time, "Dict": Dict, "Any": Any,
    })

    async def user():
        return object()

    namespace = {"router": APIRouter(), "Depends": Depends, "Request": Request,
                 "User": object, "required_user": user, "OpenAIFormatter": formatter}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), "openai", "exec"), namespace)
    app = FastAPI()
    app.include_router(namespace["router"], prefix="/v1")
    response = TestClient(app).post("/v1/chat/completions", json={"model": "test", "messages": []})
    assert response.status_code == 501
    assert "not implemented" in response.json()["error"]["message"]
