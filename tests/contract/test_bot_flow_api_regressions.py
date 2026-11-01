"""Execute real service bodies with Pydantic; DB, Flow and WS are local doubles.

The selected real imports are executed too, so missing Flow WS dependencies fail
at runtime. These tests do not establish live DB or model integration behavior.
"""

import ast
import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocketDisconnect
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aperag.schema import view_models  # noqa: E402
from aperag.utils.constant import DOC_QA_REFERENCES, DOCUMENT_URLS  # noqa: E402


def load_service(filename, name, scope):
    """Keep real methods and Flow WS imports, substitute infrastructure only."""
    path = ROOT / "aperag/service" / filename
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            selected.append(node)
        elif isinstance(node, ast.Import) and any(alias.name == "uuid" for alias in node.names):
            selected.append(node)
        elif isinstance(node, ast.ImportFrom) and node.module in {
            "aperag.flow.engine",
            "aperag.flow.parser",
            "aperag.utils.constant",
        }:
            selected.append(node)
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *selected],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    exec(compile(module, str(path), "exec"), scope)
    return scope[name]()


class Field:
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return True


class BotRow:
    id = Field()
    user = Field()
    status = Field()

    def __init__(self, **kwargs):
        self.id = "bot-regression"
        self.gmt_created = self.gmt_updated = datetime.now(timezone.utc)
        self.__dict__.update(kwargs)


def flow_payload():
    return {
        "name": "regression",
        "title": "Flow",
        "version": "1",
        "schema": {"query": {"type": "string"}},
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "data": {
                    "input": {"schema": {"type": "object"}, "values": {}},
                    "output": {"schema": {"type": "object"}},
                },
            }
        ],
        "edges": [],
    }


@pytest.fixture
def bot_harness(monkeypatch):
    row = BotRow(
        user="owner",
        title="Flow",
        type="common",
        description=None,
        status="ACTIVE",
        config="{}",
        is_default=False,
        is_protected=False,
    )
    session = SimpleNamespace(
        add=lambda bot: None,
        flush=AsyncMock(),
        refresh=AsyncMock(),
        execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: row))),
    )
    transactions = []

    async def transaction(operation):
        result = await operation(session)
        transactions.append(result)
        return result

    db_ops = SimpleNamespace(
        execute_with_transaction=transaction,
        query_bot=AsyncMock(return_value=row),
        query_bots=AsyncMock(return_value=[row]),
    )
    db_models = SimpleNamespace(
        Bot=BotRow,
        BotStatus=SimpleNamespace(ACTIVE="ACTIVE", DELETED="DELETED"),
        utc_now=lambda: datetime.now(timezone.utc),
    )
    monkeypatch.setitem(sys.modules, "aperag.db.models", db_models)
    monkeypatch.setitem(
        sys.modules, "sqlalchemy", SimpleNamespace(select=lambda model: SimpleNamespace(where=lambda *args: None))
    )
    quota = SimpleNamespace(check_and_consume_quota=AsyncMock(), release_quota=AsyncMock())
    scope = dict(
        json=json,
        view_models=view_models,
        Bot=view_models.Bot,
        BotList=view_models.BotList,
        async_db_ops=db_ops,
        quota_service=quota,
        setting_service=SimpleNamespace(get_dingtalk_bound_bot_id=AsyncMock(return_value=None)),
    )
    service = load_service("bot_service.py", "BotService", scope)
    return SimpleNamespace(service=service, row=row, session=session, transactions=transactions, quota=quota)


def assert_flow_roundtrip(bot):
    assert bot.config.flow.schema_["query"].type == "string"
    assert bot.config.flow.nodes[0].data.input.schema_.type == "object"
    assert bot.config.flow.nodes[0].data.output.schema_.type == "object"


def test_create_flow_bot_saves_aliases_and_returns_valid_response(bot_harness):
    request = view_models.BotCreate(title="Flow", type="common", config={"flow": flow_payload()})
    response = asyncio.run(bot_harness.service.create_bot("owner", request))
    assert_flow_roundtrip(response)
    saved = json.loads(bot_harness.transactions[0].config)["flow"]
    assert "schema" in saved and "schema_" not in saved
    assert "schema" in saved["nodes"][0]["data"]["input"]
    bot_harness.quota.check_and_consume_quota.assert_awaited_once()


def test_update_flow_bot_saves_aliases_and_returns_valid_response(bot_harness):
    request = view_models.BotUpdate(config={"flow": flow_payload()})
    response = asyncio.run(bot_harness.service.update_bot("owner", "bot-regression", request))
    assert_flow_roundtrip(response)
    saved = json.loads(bot_harness.row.config)["flow"]
    assert "schema" in saved and "schema_" not in saved
    assert "schema" in saved["nodes"][0]["data"]["output"]


def legacy_config():
    # Precisely reproduce the serializer that created the persisted bad config.
    return view_models.BotConfig(flow=flow_payload()).model_dump_json(exclude_none=True)


def test_existing_schema_name_config_remains_readable_in_get_and_list(bot_harness):
    bot_harness.row.config = legacy_config()
    assert_flow_roundtrip(asyncio.run(bot_harness.service.get_bot("owner", "bot-regression")))
    listing = asyncio.run(bot_harness.service.list_bots("owner"))
    assert_flow_roundtrip(listing.items[0])


def test_delete_existing_schema_name_config_returns_after_transaction(bot_harness):
    bot_harness.row.config = legacy_config()
    response = asyncio.run(bot_harness.service.delete_bot("owner", "bot-regression"))
    assert_flow_roundtrip(response)
    assert bot_harness.row.status == "DELETED"
    assert len(bot_harness.transactions) == 1
    bot_harness.quota.release_quota.assert_awaited_once()


def test_arbitrarily_invalid_flow_config_is_still_rejected(bot_harness):
    bot_harness.row.config = '{"flow":{"name":"invalid"}}'
    with pytest.raises(ValidationError):
        asyncio.run(bot_harness.service.get_bot("owner", "bot-regression"))


@pytest.mark.parametrize("execution_error", [False, True])
def test_common_websocket_reaches_flow_stream_and_preserves_errors(monkeypatch, execution_error):
    history = SimpleNamespace(add_user_message=AsyncMock())
    bot = SimpleNamespace(type="common", config=json.dumps({"flow": flow_payload()}))
    parsed_flow = object()
    parser = SimpleNamespace(parse=lambda config: parsed_flow)

    async def chunks():
        yield DOC_QA_REFERENCES + '[{"document_id":"doc"}]'
        yield DOCUMENT_URLS + "['https://example.test/document']"
        yield "SAP "
        yield "answer"

    async def execute_flow(flow, initial_data):
        assert flow is parsed_flow
        assert initial_data["query"] == "SAP query"
        if execution_error:
            raise ValueError("flow failed")
        return {}, {"answer": {"async_generator": chunks}}

    engine = SimpleNamespace(execute_flow=execute_flow, find_end_nodes=lambda flow: ["answer"])
    monkeypatch.setitem(sys.modules, "aperag.flow.parser", SimpleNamespace(FlowParser=parser))
    monkeypatch.setitem(sys.modules, "aperag.flow.engine", SimpleNamespace(FlowEngine=lambda: engine))
    documents = SimpleNamespace(associate_documents_with_message=AsyncMock(return_value=[]))
    monkeypatch.setitem(
        sys.modules, "aperag.service.chat_document_service", SimpleNamespace(chat_document_service=documents)
    )
    scope = dict(
        json=json,
        logger=logging.getLogger(__name__),
        WebSocketDisconnect=WebSocketDisconnect,
        db_models=SimpleNamespace(BotType=SimpleNamespace(AGENT="agent")),
        async_db_ops=SimpleNamespace(query_bot=AsyncMock(return_value=bot), query_chat=AsyncMock()),
        RedisChatMessageHistory=lambda *args, **kwargs: history,
        get_async_redis_client=lambda: None,
    )
    # Execute actual protocol helpers too, without Redis infrastructure imports.
    history_tree = ast.parse((ROOT / "aperag/utils/history.py").read_text(encoding="utf-8"))
    helpers = [
        node
        for node in history_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"success_response", "fail_response", "start_response", "references_response", "stop_response"}
    ]
    scope["time"] = time
    exec(compile(ast.Module(body=helpers, type_ignores=[]), "history.py", "exec"), scope)
    service = load_service("chat_service.py", "ChatService", scope)
    websocket = SimpleNamespace(
        accept=AsyncMock(),
        send_text=AsyncMock(),
        receive_text=AsyncMock(
            side_effect=[
                json.dumps({"data": "SAP query"}),
                WebSocketDisconnect(),
            ]
        ),
    )
    asyncio.run(service.handle_websocket_chat(websocket, "owner", "bot", "chat"))
    events = [json.loads(call.args[0]) for call in websocket.send_text.await_args_list]
    if execution_error:
        assert [event["type"] for event in events] == ["start", "error"]
        assert events[-1]["data"] == "flow failed"
    else:
        assert [event["type"] for event in events] == ["start", "message", "message", "references", "stop"]
        assert "".join(event["data"] for event in events if event["type"] == "message") == "SAP answer"
        assert events[-2]["data"] == [{"document_id": "doc"}]
        assert events[-2]["urls"] == ["https://example.test/document"]
    assert len({event["id"] for event in events}) == 1
    history.add_user_message.assert_awaited_once()
