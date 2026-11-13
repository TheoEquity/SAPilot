import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from aperag.chat.history.message import create_assistant_message, create_user_message
from aperag.schema import view_models as models
from aperag.service import agent_chat_service as chat

QUESTION = "FAQ 里 SAP 帐号锁定，不知道怎么提流程？"
REFERENCES = [
    {
        "text": "原文",
        "metadata": {
            "collection_id": "col",
            "document_id": "doc",
            "faq_id": "FAQBASI0002",
            "grounded": True,
        },
    }
]


@pytest.mark.parametrize("case", ["reuse", "refresh", "changed", "revoked", "correction", "paraphrase", "followup", "rejected"])
def test_faq_repetition_uses_history_only_while_source_is_current(monkeypatch, case):
    class History:
        @property
        async def messages(self):
            return entries

    skill = models.SkillConfig(id="faq", name="FAQ", category="sap_faq", collections=[{"id": "col"}])
    entries = [
        create_user_message(QUESTION, "chat", "original", files=[]),
        create_assistant_message(
            "原答复和截图",
            "chat",
            "original",
            references=REFERENCES,
            metadata={"faq": {"skill_id": "faq", "query": QUESTION, "language": "zh-CN", "sources": {"doc": "v1"}}},
        ),
    ]
    if case == "rejected":
        entries.extend(
            [
                create_user_message("这条 FAQ 不对，实际是付款失败", "chat", "correction", files=[]),
                create_assistant_message(
                    "没有匹配结果",
                    "chat",
                    "correction",
                    metadata={
                        "faq": {
                            "skill_id": "faq",
                            "query": QUESTION + "\n补充条件：实际是付款失败",
                            "correction": {"query": QUESTION, "sources": [["col", "doc", "FAQBASI0002"]]},
                        }
                    },
                ),
            ]
        )
    for index in range(80 if case not in {"refresh", "correction", "paraphrase", "followup"} else 0):
        turn = str(index)
        entries.extend(
            [
                create_user_message("其他问题", "chat", turn, files=[]),
                create_assistant_message("其他答复", "chat", turn),
            ]
        )

    service = chat.AgentChatService()
    service.history_manager.get_chat_history = AsyncMock(return_value=History())
    service._execute_skill = AsyncMock(return_value={"content": "新检索结果"})
    source_check = AsyncMock(return_value={"doc": "v1"} if case in {"reuse", "rejected"} else None)
    if case == "changed":
        source_check.return_value = {"doc": "v2"}
    monkeypatch.setattr(chat, "faq_source_versions", source_check, raising=False)
    router = AsyncMock(return_value="[FAQ_CORRECTION]" if case == "paraphrase" else "faq")
    monkeypatch.setattr(chat, "route_intent", router)
    completion = models.ModelSpec(model="model", model_service_provider="provider")
    config = models.BotConfig(
        orchestration=models.OrchestrationConfig(
            skills=[skill],
            intent_router=models.IntentRouterConfig(
                id="router",
                name="Router",
                mode="llm",
                fallback_skill_id="faq",
                prompt_template="Route",
                llm=models.IntentRouterLLMConfig(provider="provider", model="model"),
                candidate_skills=[models.CandidateSkill(skill_id="faq", label="FAQ", description="FAQ")],
            ),
        )
    )
    query = {
        "refresh": "重新查", "correction": "这条 FAQ 不对，实际是付款失败",
        "paraphrase": "这个跟我遇到的不是一回事，我这边是付款失败。",
        "followup": "能详细说下第二步吗？",
    }.get(case, QUESTION)
    queue = SimpleNamespace(put=AsyncMock(), close=AsyncMock())
    result = asyncio.run(
        service.process_agent_message(
            models.AgentMessage(query=query, collections=[], completion=completion, language="zh-CN"),
            "user",
            "chat",
            "current",
            queue,
            bot_config=config,
        )
    )

    if case == "reuse":
        assert result["content"] == "原答复和截图"
        assert result["references"] == REFERENCES
        router.assert_not_awaited()
        service._execute_skill.assert_not_awaited()
        assert [call.args[0]["type"] for call in queue.put.await_args_list] == ["start", "message", "stop"]
    else:
        assert result["content"] == "新检索结果"
        service._execute_skill.assert_awaited_once()
        expected_query = {
            "correction": QUESTION + "\n补充条件：实际是付款失败",
            "paraphrase": QUESTION + "\n补充条件：" + query,
            "followup": query,
        }.get(case, QUESTION)
        assert service._execute_skill.await_args.args[1].query == expected_query
        if case == "refresh":
            assert result["query"] == "重新查"
            source_check.assert_not_awaited()
        if case in {"paraphrase", "followup"}:
            assert router.await_args.kwargs["faq_correction_context"] == (QUESTION, "原答复和截图")
        if case in {"correction", "paraphrase", "rejected"}:
            assert service._execute_skill.await_args.kwargs["rejected_faq_sources"] == {("col", "doc", "FAQBASI0002")}
            source_check.assert_not_awaited()
        if case in {"correction", "paraphrase"}:
            assert result["query"] == query
            assert result["faq"]["correction"]["query"] == QUESTION
        if case == "followup":
            assert "rejected_faq_sources" not in service._execute_skill.await_args.kwargs
            assert "faq" not in result
