"""Execute service definitions with real API models and isolated DB/LLM transports.

The host's OpenAPI environment lacks the runtime infrastructure dependencies.
AST loading substitutes imports only; tested method bodies are unchanged. These
tests cover DB-bound values and evaluation orchestration, not SQL or model calls.
"""

import ast
import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aperag.chat.history.message import create_assistant_message  # noqa: E402
from aperag.schema import view_models  # noqa: E402


def load_class(path, name, namespace, methods=None):
    source = ROOT / path
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    definition = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
    if methods is not None:
        definition.body = [node for node in definition.body if getattr(node, "name", None) in methods]
        assert len(definition.body) == len(methods)
    module = ast.Module(
        body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), definition],
        type_ignores=[],
    )
    exec(compile(ast.fix_missing_locations(module), str(source), "exec"), namespace)
    return namespace[name]


@pytest.mark.parametrize("operation", ["create_set", "add", "update"])
@pytest.mark.parametrize("question_type", ["FACTUAL", "INFERENTIAL", "USER_DEFINED", None, "omitted"])
def test_question_type_reaches_persistence_as_scalar(operation, question_type):
    service_class = load_class(
        "aperag/service/question_set_service.py",
        "QuestionSetService",
        {"Question": SimpleNamespace, "QuestionSet": SimpleNamespace},
        {"create_question_set", "add_questions", "update_question"},
    )
    service = service_class()
    db = SimpleNamespace(
        create_question_set=AsyncMock(), create_questions_in_bulk=AsyncMock(), update_question=AsyncMock()
    )
    service.db_ops = db
    payload = {"question_text": "SAP question", "ground_truth": "Verified answer"}
    if question_type != "omitted":
        payload["question_type"] = question_type

    if operation == "create_set":
        request = view_models.QuestionSetCreate(name="Regression", questions=[payload])
        asyncio.run(service.create_question_set(request, "user-a"))
        saved = db.create_question_set.await_args.args[1][0]
        persisted_type = saved.question_type
        assert db.create_question_set.await_args.args[0].user_id == "user-a"
    elif operation == "add":
        asyncio.run(service.add_questions("qs-a", view_models.QuestionsAdd(questions=[payload])))
        saved = db.create_questions_in_bulk.await_args.args[0][0]
        persisted_type = saved.question_type
        assert saved.question_set_id == "qs-a"
    else:
        asyncio.run(service.update_question("q-a", view_models.QuestionUpdate(**payload)))
        q_id, text, truth, persisted_type = db.update_question.await_args.args
        assert (q_id, text, truth) == ("q-a", "SAP question", "Verified answer")

    expected = None if question_type in (None, "omitted") else question_type
    assert persisted_type == expected
    assert persisted_type is None or isinstance(persisted_type, str)


class EmptyHistory:
    @property
    async def messages(self):
        return []


@pytest.fixture
def evaluation_harness():
    scope = {
        "asyncio": asyncio,
        "json": json,
        "uuid": uuid,
        "logger": logging.getLogger(__name__),
        "view_models": view_models,
        "create_assistant_message": create_assistant_message,
        "format_stream_start": lambda message_id: {"type": "start"},
        "format_stream_content": lambda message_id, content: {"type": "message", "data": content},
        "format_stream_end": lambda message_id, **kwargs: {"type": "stop"},
        "route_intent": AsyncMock(return_value="sap-skill"),
        "prompt_template_service": SimpleNamespace(
            resolve_agent_system_prompt=AsyncMock(return_value="User's system prompt"),
            resolve_agent_query_prompt=AsyncMock(return_value="User's query prompt"),
        ),
        "agent_event_listener": SimpleNamespace(unregister_listener=AsyncMock()),
    }
    load_class("aperag/agent/agent_message_queue.py", "AgentMessageQueue", scope)
    service_class = load_class(
        "aperag/service/agent_chat_service.py",
        "AgentChatService",
        scope,
        {"chat_for_evaluation", "process_agent_message"},
    )
    service = service_class()
    service.memory_manager = SimpleNamespace(create_memory_from_history=AsyncMock(return_value=[]))
    service.history_manager = SimpleNamespace(get_chat_history=AsyncMock(return_value=EmptyHistory()))
    service.skill_context_buffers = {}
    service._get_agent_session = AsyncMock()
    service.register_message_queue = AsyncMock(return_value="trace-evaluation")
    service._format_exception_to_error_response = lambda error, language: {"type": "error", "data": str(error)}
    service.db_ops = SimpleNamespace(query_bots=AsyncMock(return_value=[]))
    executed = []

    async def execute_skill(skill_id, message, user, chat_id, message_id, queue, query_prompt, **kwargs):
        executed.append((skill_id, message, user, query_prompt, kwargs))
        return {"query": message.query, "content": "SAP skill answer", "references": []}

    service._execute_skill = execute_skill
    return SimpleNamespace(service=service, executed=executed, scope=scope)


def configured_bot(**overrides):
    config = view_models.BotConfig(
        agent=view_models.Agent(
            completion=view_models.ModelSpec(model="bot-model"),
            collections=[view_models.Collection(id="bot-default-collection")],
        ),
        orchestration=view_models.OrchestrationConfig(
            skills=[view_models.SkillConfig(id="sap-skill", name="SAP")],
            intent_router=view_models.IntentRouterConfig(
                id="router",
                name="Router",
                llm=view_models.IntentRouterLLMConfig(provider="intent-provider", model="intent-model"),
                prompt_template="Classify {query}",
                fallback_skill_id="sap-skill",
                candidate_skills=[view_models.CandidateSkill(skill_id="sap-skill", label="SAP")],
            )
        ),
    )
    return SimpleNamespace(
        **{"id": "default-bot", "type": "agent", "is_default": True, "config": config.model_dump_json(), **overrides}
    )


def evaluate(harness):
    return asyncio.run(
        asyncio.wait_for(
            harness.service.chat_for_evaluation(
                query="SAP question",
                user_id="user-a",
                model_name="evaluation-model",
                model_service_provider="evaluation-provider",
                custom_llm_provider=None,
                collections=[view_models.Collection(id="evaluation-collection")],
                language="zh-CN",
            ),
            timeout=3,
        )
    )


def test_evaluation_executes_default_agent_orchestration_and_keeps_requested_model_and_collection(evaluation_harness):
    h = evaluation_harness
    bot = configured_bot()
    h.service.db_ops.query_bots.return_value = [
        configured_bot(id="newer-nondefault", is_default=False),
        configured_bot(id="default-flow", type="common"),
        bot,
    ]
    result = evaluate(h)
    assert result.get_main_content() == "SAP skill answer"
    h.service.db_ops.query_bots.assert_awaited_once_with(["user-a"])
    skill_id, message, user, query_prompt, kwargs = h.executed[0]
    assert (skill_id, user, query_prompt) == ("sap-skill", "user-a", "User's query prompt")
    assert message.completion.model == "evaluation-model"
    assert message.completion.model_service_provider == "evaluation-provider"
    assert [collection.id for collection in message.collections] == ["evaluation-collection"]
    assert message.language == "zh-CN"
    assert kwargs["resolved_system_prompt"] == "User's system prompt"
    assert kwargs["orchestration"].intent_router.llm.model == "intent-model"
    for resolver in ("resolve_agent_system_prompt", "resolve_agent_query_prompt"):
        getattr(h.scope["prompt_template_service"], resolver).assert_awaited_once_with(bot=bot, user_id="user-a")
    h.scope["agent_event_listener"].unregister_listener.assert_awaited_once_with("trace-evaluation")


@pytest.mark.parametrize("bots", [[], [configured_bot(is_default=False)], [configured_bot(type="common")]])
def test_evaluation_does_not_invent_or_select_another_bot_configuration(evaluation_harness, bots):
    h = evaluation_harness
    h.service.db_ops.query_bots.return_value = bots
    result = evaluate(h)
    assert h.executed == []
    assert "orchestration configuration is missing" in result.get_main_content()


@pytest.mark.parametrize("config", ["{invalid", "[]", '{"agent": {"completion": "invalid"}}'])
def test_evaluation_invalid_default_config_does_not_execute_a_skill(evaluation_harness, config):
    h = evaluation_harness
    h.service.db_ops.query_bots.return_value = [configured_bot(config=config)]
    result = evaluate(h)
    assert h.executed == []
    assert "orchestration configuration is missing" in result.get_main_content()
