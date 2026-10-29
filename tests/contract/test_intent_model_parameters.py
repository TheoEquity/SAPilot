"""Execute real service/router/session definition ASTs without importing the runtime stack.

Only import-time infrastructure is substituted. RequestParams, SimpleMemory,
DB/LLM/history/queue transports and MCP initialization are local test doubles;
this suite does not execute the third-party SDK or make HTTP calls.
"""

import ast
import asyncio
import logging
import os
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aperag.exceptions import BusinessException, ErrorCode  # noqa: E402
from aperag.schema import view_models as models  # noqa: E402


def execute_definitions(relative_path, names, namespace, methods=None):
    """Compile real definitions, preserving bodies, decorators and source lines."""
    path = ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    selected = [node for node in tree.body if getattr(node, "name", None) in names]
    assert len(selected) == len(names)
    if methods:
        for node in selected:
            if isinstance(node, ast.ClassDef) and node.name in methods:
                node.body = [item for item in node.body if getattr(item, "name", None) in methods[node.name]]
                assert len(node.body) == len(methods[node.name])
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *selected],
        type_ignores=[],
    )
    ast.fix_missing_locations(module)
    exec(compile(module, str(path), "exec"), namespace)
    return namespace


class History:
    def __init__(self):
        self.entries = [
            SimpleNamespace(to_openai_format=lambda include_tool_results, i=i: [{"role": "user", "content": str(i)}])
            for i in range(6)
        ]

    @property
    async def messages(self):
        return self.entries


def stream_start(message_id):
    return {"type": "start", "id": message_id}


def stream_content(message_id, text):
    return {"type": "message", "id": message_id, "data": text}


def stream_end(message_id, **kwargs):
    return {"type": "stop", "id": message_id, **kwargs}


@pytest.fixture
def harness(monkeypatch):
    exception_scope = execute_definitions(
        "aperag/agent/exceptions.py",
        {"AgentError", "AgentConfigurationError"},
        {
            "BusinessException": BusinessException,
            "ErrorCode": ErrorCode,
            "Optional": Optional,
            "Dict": Dict,
            "Any": Any,
        },
    )
    # Real dataclass, loaded directly to avoid importing aperag.agent.__init__.
    config_scope = {"__name__": __name__}
    from dataclasses import dataclass

    config_scope.update(dataclass=dataclass)
    execute_definitions("aperag/agent/agent_config.py", {"AgentConfig"}, config_scope)
    llm = SimpleNamespace(generate_str=AsyncMock(return_value="selected"), history=None)
    manager_scope = {
        "time": time,
        "logger": logging.getLogger(__name__),
        "_chat_sessions": {},
        "AgentConfigurationError": exception_scope["AgentConfigurationError"],
    }
    execute_definitions(
        "aperag/agent/agent_session_manager.py", {"ChatSession", "get_or_create_session"}, manager_scope
    )
    initialized = []

    async def initialize(session):
        initialized.append(session.config)
        session.llm = llm
        session._ready = True

    monkeypatch.setattr(manager_scope["ChatSession"], "initialize", initialize)
    manager = SimpleNamespace(get_or_create_session=AsyncMock(side_effect=manager_scope["get_or_create_session"]))
    scope = {
        "view_models": models,
        "RequestParams": SimpleNamespace,
        "SimpleMemory": list,
        "AgentConfig": config_scope["AgentConfig"],
        "agent_session_manager": manager,
        "AgentConfigurationError": exception_scope["AgentConfigurationError"],
        "logger": logging.getLogger(__name__),
        "os": os,
        "re": re,
        "format_stream_start": stream_start,
        "format_stream_content": stream_content,
        "format_stream_end": stream_end,
    }
    execute_definitions("aperag/agent/intent_router.py", {"route_intent", "try_hard_rules_match"}, scope)
    execute_definitions(
        "aperag/service/agent_chat_service.py",
        {"AgentChatService"},
        scope,
        {"AgentChatService": {"process_agent_message", "_get_agent_session", "_build_faq_choice_end_response"}},
    )
    service = scope["AgentChatService"]()
    history = History()
    service.history_manager = SimpleNamespace(get_chat_history=AsyncMock(return_value=history))
    service.memory_manager = SimpleNamespace(create_memory_from_history=AsyncMock(return_value=[]))
    service.skill_context_buffers = {}
    service._execute_skill = AsyncMock(return_value={"content": "skill result"})
    service.db_ops = SimpleNamespace(
        query_llm_provider_by_name=AsyncMock(return_value=SimpleNamespace(base_url="https://intent.invalid/v1")),
        query_provider_api_key=AsyncMock(return_value="fake-intent-key"),
        query_api_keys=AsyncMock(return_value=[SimpleNamespace(key="fake-system-key")]),
        create_api_key=AsyncMock(),
    )
    completion = models.ModelSpec(
        model="answer-model", model_service_provider="answer-provider", temperature=0.82, max_tokens=8000
    )
    message = models.AgentMessage(query="SAP query", collections=[], completion=completion, language="zh-CN")
    router = models.IntentRouterConfig(
        id="router",
        name="Router",
        mode="llm",
        llm=models.IntentRouterLLMConfig(
            provider="intent-provider", model="intent-model", temperature=0.17, max_tokens=1379
        ),
        prompt_template="Classify {{query}}\n{{skills}}",
        fallback_skill_id="fallback",
        candidate_skills=[
            models.CandidateSkill(skill_id="selected", label="Selected", description="SAP"),
            models.CandidateSkill(skill_id="disabled", label="Disabled", enabled=False),
        ],
    )
    bot = models.BotConfig(
        agent=models.Agent(completion=completion), orchestration=models.OrchestrationConfig(intent_router=router)
    )
    queue = SimpleNamespace(put=AsyncMock(), close=AsyncMock())
    return SimpleNamespace(
        service=service,
        message=message,
        router=router,
        bot=bot,
        queue=queue,
        llm=llm,
        manager=manager,
        manager_scope=manager_scope,
        initialized=initialized,
        config_class=config_scope["AgentConfig"],
        history=history,
        rule_match=scope["try_hard_rules_match"],
    )


def run(h):
    return asyncio.run(
        h.service.process_agent_message(
            h.message,
            "user-a",
            "chat-a",
            "message-a",
            h.queue,
            bot_config=h.bot,
            resolved_system_prompt="System prompt",
            resolved_query_prompt="Answer prompt",
        )
    )


def assert_routed(h, skill_id):
    h.service._execute_skill.assert_awaited_once()
    args, kwargs = h.service._execute_skill.await_args
    assert args[0] == skill_id
    assert args[1].completion == h.message.completion
    assert args[2:5] == ("user-a", "chat-a", "message-a")
    assert kwargs["orchestration"] is h.bot.orchestration
    h.queue.close.assert_awaited_once()


@pytest.mark.parametrize("max_tokens", [1, 1379, None])
@pytest.mark.parametrize("temperature", [0, 0.17])
def test_intent_provider_configuration_and_request_parameters(harness, max_tokens, temperature):
    h = harness
    if max_tokens is None:
        h.router.llm = models.IntentRouterLLMConfig(provider="intent-provider", model="intent-model", temperature=0.17)
    else:
        h.router.llm.max_tokens = max_tokens
    h.router.llm.temperature = temperature
    original = h.message.model_dump()
    assert run(h) == {"content": "skill result"}
    h.service.db_ops.query_llm_provider_by_name.assert_awaited_once_with("intent-provider")
    h.service.db_ops.query_provider_api_key.assert_awaited_once_with(
        "intent-provider", user_id="user-a", need_public=True
    )
    config = h.initialized[0]
    assert (config.provider_name, config.api_key, config.base_url, config.default_model) == (
        "intent-provider",
        "fake-intent-key",
        "https://intent.invalid/v1",
        "intent-model",
    )
    assert (config.user_id, config.chat_id, config.language, config.instruction) == (
        "user-a",
        "chat-a",
        "zh-CN",
        "System prompt",
    )
    h.llm.generate_str.assert_awaited_once()
    prompt, params = h.llm.generate_str.await_args.args
    assert params.model == "intent-model"
    assert params.maxTokens == (1024 if max_tokens is None else max_tokens)
    assert params.temperature == temperature
    assert (params.use_history, params.max_iterations, params.user, params.tool_filter) == (
        False,
        1,
        "user-a",
        {"aperag": set()},
    )
    assert h.message.model_dump() == original
    assert [msg["content"] for msg in h.llm.history] == ["2", "3", "4", "5"]
    description = "- selected: Selected - SAP"
    assert prompt == (
        f"Classify SAP query\n{description}\n\n"
        "Authoritative candidate skills (you must choose one exact skill_id from this list):\n"
        f"{description}\n\nCurrent user input:\nSAP query\n\n"
        "Output exactly one skill_id from the authoritative candidate list above."
    )
    assert_routed(h, "selected")


def test_same_provider_warm_cache_uses_explicit_intent_request_model(harness):
    h = harness
    h.message.completion.model_service_provider = "intent-provider"
    config = h.config_class(
        user_id="user-a",
        chat_id="chat-a",
        provider_name="intent-provider",
        api_key="fake-intent-key",
        base_url="https://intent.invalid/v1",
        default_model="old-answer-model",
        instruction="Old instruction",
    )
    warmed = asyncio.run(h.manager.get_or_create_session(config))
    h.manager.get_or_create_session.reset_mock()
    assert run(h) == {"content": "skill result"}
    assert len(h.initialized) == 1
    assert h.manager_scope["_chat_sessions"][config.get_session_key()] is warmed
    assert warmed.config.default_model == "old-answer-model"  # Existing cache is deliberately unchanged.
    assert h.manager.get_or_create_session.await_args.args[0].default_model == "intent-model"
    assert h.llm.generate_str.await_args.args[1].model == "intent-model"
    assert h.llm.generate_str.await_args.args[1].maxTokens == 1379
    assert_routed(h, "selected")


@pytest.mark.parametrize(
    "response,expected",
    [
        (" selected \n", "selected"),
        ("disabled", "fallback"),
        ("unknown", "fallback"),
        ("", "fallback"),
        (None, "fallback"),
    ],
)
def test_classification_output_and_fallback_stay_unchanged(harness, response, expected):
    h = harness
    h.llm.generate_str.return_value = response
    run(h)
    assert_routed(h, expected)


@pytest.mark.parametrize(
    "forced,mode,expected,classifies",
    [("forced", "rules+llm", "forced", False), (None, "rules+llm", "first", False), (None, "llm", "selected", True)],
)
def test_forced_skill_and_first_matching_rule_priority(harness, forced, mode, expected, classifies):
    h = harness
    h.message.force_skill_id = forced
    h.router.mode = mode
    h.router.rules = [
        models.IntentRouterRule(rule_type="keyword", value="SAP", target_skill_id="first"),
        models.IntentRouterRule(rule_type="keyword", value="query", target_skill_id="second"),
    ]
    run(h)
    assert h.llm.generate_str.await_count == int(classifies)
    assert h.service.db_ops.query_llm_provider_by_name.await_count == int(classifies)
    assert_routed(h, expected)


def test_model_exception_propagates_without_executing_skill_and_closes_queue(harness):
    h = harness
    failure = RuntimeError("synthetic classification failure")
    h.llm.generate_str.side_effect = failure
    with pytest.raises(RuntimeError) as caught:
        run(h)
    assert caught.value is failure
    h.service._execute_skill.assert_not_awaited()
    h.llm.generate_str.assert_awaited_once()
    h.queue.close.assert_awaited_once()


@pytest.mark.parametrize("missing", ["provider", "key"])
def test_missing_provider_or_key_stops_before_model_and_closes_queue(harness, missing, caplog):
    h = harness
    if missing == "provider":
        h.service.db_ops.query_llm_provider_by_name.return_value = None
    else:
        h.service.db_ops.query_provider_api_key.return_value = None
    # Characterize the existing failure boundary without approving its exception
    # type: _get_agent_session currently calls AgentConfigurationError with the
    # wrong signature. Correcting that pre-existing error is outside this batch.
    with pytest.raises(Exception):
        run(h)
    h.service.db_ops.query_llm_provider_by_name.assert_awaited_once_with("intent-provider")
    if missing == "provider":
        assert "Provider 'intent-provider' not found in database" in caplog.text
        h.service.db_ops.query_provider_api_key.assert_not_awaited()
    else:
        assert "No API key available for provider 'intent-provider'" in caplog.text
        h.service.db_ops.query_provider_api_key.assert_awaited_once_with(
            "intent-provider", user_id="user-a", need_public=True
        )
    h.manager.get_or_create_session.assert_not_awaited()
    h.llm.generate_str.assert_not_awaited()
    h.service._execute_skill.assert_not_awaited()
    h.queue.close.assert_awaited_once()


def test_configured_token_budget_reaches_classification_call(harness):
    h = harness
    run(h)
    assert h.llm.generate_str.await_args.args[1].maxTokens == 1379


def test_bot_completion_fallback_is_preserved_for_skill_execution(harness):
    h = harness
    h.message.completion = None
    original = h.bot.agent.completion.model_dump()
    run(h)
    executed_message = h.service._execute_skill.await_args.args[1]
    assert executed_message.completion.model_dump() == original
    assert h.bot.agent.completion.model_dump() == original
    assert h.message.completion is None
    assert h.initialized[0].default_model == "intent-model"
    h.queue.close.assert_awaited_once()


@pytest.mark.parametrize(
    "query,rules,expected",
    [
        ("请 查 一下！SAP", [{"value": "查SAP", "target_skill_id": "normalized"}], "normalized"),
        ("SAP ERROR", [{"value": "sap error", "target_skill_id": "case"}], "case"),
        ("SAP Error 42", [{"rule_type": "regex", "value": r"error\s+\d+", "target_skill_id": "regex"}], "regex"),
        (
            "SAP",
            [
                {"value": "SAP", "target_skill_id": "disabled", "enabled": False},
                {"rule_type": "regex", "value": "[", "target_skill_id": "invalid"},
                {"rule_type": "unknown", "value": "SAP", "target_skill_id": "unknown"},
                {"value": "", "target_skill_id": "empty-value"},
                {"value": "SAP", "target_skill_id": ""},
                {"value": "SAP", "target_skill_id": "first"},
                {"value": "SAP", "target_skill_id": "second"},
            ],
            "first",
        ),
        ("SAP", [{"value": "ABAP", "target_skill_id": "absent"}], None),
    ],
)
def test_hard_rule_algorithm(harness, query, rules, expected):
    assert harness.rule_match(query, rules) == expected


def test_unmatched_rules_classify_once(harness):
    h = harness
    h.router.mode = "rules+llm"
    h.router.rules = [models.IntentRouterRule(rule_type="keyword", value="ABAP", target_skill_id="absent")]
    run(h)
    h.llm.generate_str.assert_awaited_once()
    assert_routed(h, "selected")


@pytest.mark.parametrize("existing_skill", ["other", "selected"])
def test_skill_context_switch_and_continuation(harness, existing_skill):
    h = harness
    previous = {"skill_id": existing_skill, "messages": [object()]}
    h.service.skill_context_buffers["chat-a"] = previous
    run(h)
    current = h.service.skill_context_buffers["chat-a"]
    if existing_skill == "selected":
        assert current is previous
    else:
        assert current is not previous
        assert current == {"skill_id": "selected", "messages": h.history.entries[-4:]}
    assert_routed(h, "selected")


@pytest.mark.parametrize(
    "missing,expected",
    [
        ("orchestration", "Bot orchestration configuration is missing. Please configure intent router and skills in bot settings."),
        ("router", "Intent router is not configured. Please configure the intent router."),
        ("fallback_skill_id", "Intent router configuration incomplete. Missing: fallback skill"),
        ("candidate_skills", "Intent router configuration incomplete. Missing: candidate skills"),
        ("llm", "Intent router configuration incomplete. Missing: intent model"),
        ("prompt_template", "Intent router configuration incomplete. Missing: prompt template"),
    ],
)
def test_configuration_checks_still_precede_forced_routing(harness, missing, expected):
    h = harness
    h.message.force_skill_id = "forced"
    if missing == "orchestration":
        h.bot.orchestration = None
    elif missing == "router":
        h.bot.orchestration.intent_router = None
    else:
        setattr(h.router, missing, [] if missing == "candidate_skills" else None)
    assert run(h) == {"query": "SAP query", "content": expected, "references": []}
    assert h.queue.put.await_args_list == [
        ((stream_start("message-a"),), {}),
        ((stream_content("message-a", expected),), {}),
        ((stream_end("message-a", references=[], urls=[]),), {}),
    ]
    h.service.db_ops.query_llm_provider_by_name.assert_not_awaited()
    h.llm.generate_str.assert_not_awaited()
    h.service._execute_skill.assert_not_awaited()
    assert h.service.skill_context_buffers == {}
    h.queue.close.assert_awaited_once()


def test_faq_end_bypasses_router_configuration(harness):
    h = harness
    h.message.action = "faq_end"
    h.bot.orchestration = None
    expected = "好的，本次基于知识库标准答案的解答已结束。"
    assert run(h) == {"query": "SAP query", "content": expected, "references": []}
    h.service.history_manager.get_chat_history.assert_awaited_once_with("chat-a")
    h.service.memory_manager.create_memory_from_history.assert_awaited_once_with(h.history, context_limit=4)
    assert [call.args[0]["type"] for call in h.queue.put.await_args_list] == ["start", "message", "stop"]
    h.service._execute_skill.assert_not_awaited()
    h.llm.generate_str.assert_not_awaited()
    h.queue.close.assert_awaited_once()


def test_whitespace_prompt_retains_original_default_and_authoritative_suffix(harness):
    h = harness
    h.router.prompt_template = "   "
    run(h)
    description = "- selected: Selected - SAP"
    assert h.llm.generate_str.await_args.args[0] == (
        f"Classify into one skill:\n{description}\n\nQuery: SAP query\nReply with skill_id only.\n\n"
        "Authoritative candidate skills (you must choose one exact skill_id from this list):\n"
        f"{description}\n\nCurrent user input:\nSAP query\n\n"
        "Output exactly one skill_id from the authoritative candidate list above."
    )
    assert_routed(h, "selected")
