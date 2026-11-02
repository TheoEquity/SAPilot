"""Real WebSocket boundaries, queue and Starlette socket with isolated generation.

AST loading replaces import-time infrastructure. No DB, MCP or model is used.
"""

import ast
import asyncio
import json
import logging
import runpy
import sys
import time
import uuid
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.websockets import WebSocket, WebSocketDisconnect

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def boundary(monkeypatch):
    path = ROOT / "aperag/service/agent_chat_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "AgentChatService")
    methods = {
        "handle_websocket_agent_chat",
        "_handle_single_message",
        "_consume_messages_from_queue",
        "_stream_message_content",
    }
    cls.body = [node for node in cls.body if getattr(node, "name", None) in methods]
    for node in cls.body:
        node.decorator_list = []
    document_module = ModuleType("aperag.service.chat_document_service")
    document_module.chat_document_service = SimpleNamespace(associate_documents_with_message=AsyncMock(return_value=[]))
    monkeypatch.setitem(sys.modules, document_module.__name__, document_module)
    listener = SimpleNamespace(unregister_listener=AsyncMock())
    namespace = dict(
        asyncio=asyncio,
        json=json,
        time=time,
        uuid=uuid,
        logger=logging.getLogger("test.chat-cancel"),
        WebSocketDisconnect=WebSocketDisconnect,
        AgentMessageQueue=runpy.run_path(str(ROOT / "aperag/agent/agent_message_queue.py"))["AgentMessageQueue"],
        agent_event_listener=listener,
        add_trace_attributes=Mock(),
        format_processing_error=lambda message, language: {"type": "error", "message": message},
        prompt_template_service=SimpleNamespace(
            resolve_agent_system_prompt=AsyncMock(return_value="system"),
            resolve_agent_query_prompt=AsyncMock(return_value="query"),
        ),
    )
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), cls],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    exec(compile(module, str(path), "exec"), namespace)
    service = namespace["AgentChatService"]()
    service.register_message_queue = AsyncMock(return_value="existing-trace")
    service._save_conversation_history = AsyncMock()
    service._format_exception_to_error_response = lambda error, language: {"type": "error", "message": str(error)}
    service.db_ops = SimpleNamespace(query_bot=AsyncMock(return_value=SimpleNamespace(config=None)))
    service._parse_websocket_message = lambda data: (SimpleNamespace(query=data, files=[], language="en-US"), None)
    return SimpleNamespace(service=service, listener=listener)


class Socket:
    """ASGI transport that records frames and detects overlapping receives."""

    def __init__(self):
        self.events = asyncio.Queue()
        self.events.put_nowait({"type": "websocket.connect"})
        self.sent = []
        self.active_receives = 0
        self.max_receives = 0
        self.read_texts = []
        self.websocket = WebSocket({"type": "websocket"}, self.receive, self.send)

    async def receive(self):
        self.active_receives += 1
        self.max_receives = max(self.max_receives, self.active_receives)
        try:
            event = await self.events.get()
            if event["type"] == "websocket.receive":
                self.read_texts.append(event["text"])
            return event
        finally:
            self.active_receives -= 1

    async def send(self, event):
        self.sent.append(event)

    def close(self):
        self.events.put_nowait({"type": "websocket.disconnect", "code": 1000})

    def message(self, text):
        self.events.put_nowait({"type": "websocket.receive", "text": text})


async def finish_promptly(task):
    done, _ = await asyncio.wait({task}, timeout=0.3)
    assert task in done, "connection termination must not wait for blocked generation"
    return await task


@pytest.mark.parametrize("disconnect_source", ["receive", "consumer", "parent"])
def test_disconnect_cancels_blocked_generation_and_cleans_listener(boundary, caplog, disconnect_source):
    async def scenario():
        service = boundary.service
        baseline_tasks = asyncio.all_tasks()
        socket = Socket()
        await socket.websocket.accept()
        started = asyncio.Event()
        stopped = asyncio.Event()

        async def generate(*args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        async def disconnected_consumer(*args):
            await started.wait()
            raise WebSocketDisconnect(1000)

        service.process_agent_message = generate
        if disconnect_source == "consumer":
            service._consume_messages_from_queue = disconnected_consumer
        task = asyncio.create_task(
            service._handle_single_message(
                socket.websocket,
                SimpleNamespace(files=[], language="en-US"),
                "user",
                "chat-test",
            )
        )
        try:
            await asyncio.wait_for(started.wait(), 1)
            if disconnect_source == "receive":
                socket.close()
            elif disconnect_source == "parent":
                task.cancel()
            try:
                await finish_promptly(task)
            except (WebSocketDisconnect, asyncio.CancelledError):
                pass
            assert stopped.is_set(), "blocked local generation must be cancelled and awaited"
            assert socket.active_receives == 0
            assert socket.max_receives <= 1
            assert not asyncio.all_tasks().difference(baseline_tasks)
            assert not [frame for frame in socket.sent if frame["type"] == "websocket.send"]
            service._save_conversation_history.assert_not_awaited()
            boundary.listener.unregister_listener.assert_awaited_once_with("existing-trace")
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    with caplog.at_level(logging.INFO, logger="test.chat-cancel"):
        asyncio.run(scenario())
    records = [record for record in caplog.records if record.name == "test.chat-cancel"]
    assert [record.msg for record in records] == ["chat.message.started", "chat.message.cancelled"]
    assert all(record.levelno == logging.INFO for record in records)


@pytest.mark.parametrize("failure", [None, "producer", "consumer"])
def test_completed_or_failed_generation_preserves_history_and_error_boundary(boundary, failure):
    async def scenario():
        service = boundary.service
        baseline_tasks = asyncio.all_tasks()
        socket = Socket()
        await socket.websocket.accept()
        stopped = asyncio.Event()

        async def generate(message, user, chat, message_id, queue, **kwargs):
            try:
                if failure == "producer":
                    raise ValueError("generation failed")
                if failure == "consumer":
                    await asyncio.Event().wait()
                await queue.put({"type": "message", "data": "ok"})
                return {"query": "question", "content": "ok", "references": []}
            finally:
                stopped.set()
                await queue.close()

        async def failing_consumer(*args):
            raise ValueError("stream failed")

        service.process_agent_message = generate
        if failure == "consumer":
            service._consume_messages_from_queue = failing_consumer
        task = asyncio.create_task(
            service._handle_single_message(
                socket.websocket,
                SimpleNamespace(files=[], language="en-US"),
                "user",
                "chat-test",
            )
        )
        try:
            await finish_promptly(task)
            assert stopped.is_set()
            assert socket.active_receives == 0
            assert not asyncio.all_tasks().difference(baseline_tasks)
            frames = [json.loads(frame["text"]) for frame in socket.sent if frame["type"] == "websocket.send"]
            if failure:
                assert frames == [
                    {"type": "error", "message": "generation failed" if failure == "producer" else "stream failed"}
                ]
                service._save_conversation_history.assert_not_awaited()
            else:
                assert [frame["data"] for frame in frames] == ["ok"]
                service._save_conversation_history.assert_awaited_once()
            boundary.listener.unregister_listener.assert_awaited_once_with("existing-trace")
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def test_disconnect_during_failure_cleanup_does_not_send_error_or_save(boundary, caplog):
    async def scenario():
        service = boundary.service
        socket = Socket()
        await socket.websocket.accept()
        started = asyncio.Event()

        async def generate(*args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                socket.close()

        async def failing_consumer(*args):
            await started.wait()
            raise ValueError("stream failed while closing")

        service.process_agent_message = generate
        service._consume_messages_from_queue = failing_consumer
        task = asyncio.create_task(
            service._handle_single_message(
                socket.websocket,
                SimpleNamespace(files=[], language="en-US"),
                "user",
                "chat-test",
            )
        )
        try:
            try:
                await finish_promptly(task)
            except WebSocketDisconnect:
                pass
            assert not [frame for frame in socket.sent if frame["type"] == "websocket.send"]
            service._save_conversation_history.assert_not_awaited()
            boundary.listener.unregister_listener.assert_awaited_once_with("existing-trace")
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    with caplog.at_level(logging.INFO, logger="test.chat-cancel"):
        asyncio.run(scenario())
    records = [record for record in caplog.records if record.name == "test.chat-cancel"]
    assert [record.msg for record in records] == ["chat.message.started", "chat.message.cancelled"]


def test_early_next_message_is_preserved_without_concurrent_receive(boundary):
    async def scenario():
        service = boundary.service
        socket = Socket()
        await socket.websocket.accept()
        first_started = asyncio.Event()
        release_first = asyncio.Event()
        second_completed = asyncio.Event()
        queries = []

        async def generate(message, user, chat, message_id, queue, **kwargs):
            try:
                queries.append(message.query)
                if message.query == "first":
                    first_started.set()
                    await release_first.wait()
                await queue.put({"type": "message", "data": "ok"})
                return {"query": message.query, "content": "ok", "references": []}
            finally:
                await queue.close()

        async def save(*args):
            if args[3] == "second":
                second_completed.set()

        service.process_agent_message = generate
        service._save_conversation_history.side_effect = save
        task = asyncio.create_task(service.handle_websocket_agent_chat(socket.websocket, "user", "bot", "chat"))
        try:
            socket.message("first")
            await asyncio.wait_for(first_started.wait(), 1)
            socket.message("second")
            await asyncio.sleep(0.02)
            assert socket.read_texts == ["first", "second"], "watcher must buffer the early frame"
            release_first.set()
            await asyncio.wait_for(second_completed.wait(), 1)
            socket.close()
            await finish_promptly(task)
            assert queries == ["first", "second"]
            assert socket.read_texts == ["first", "second"]
            assert socket.max_receives == 1
            assert socket.active_receives == 0
            assert service._save_conversation_history.await_count == 2
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())
