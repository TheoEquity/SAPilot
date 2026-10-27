"""Intent routing must see bounded, chat-local context without pinning the Skill."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from mcp_agent.workflows.llm.augmented_llm import SimpleMemory

from aperag.chat.history.message import create_assistant_message, create_user_message
from aperag.schema import view_models
from aperag.service.agent_chat_service import AgentChatService


class ChatHistory:
    def __init__(self, messages):
        self._messages = messages

    @property
    async def messages(self):
        return self._messages


class RecordingRouter:
    """Record effective model input using the adapter's use_history contract."""

    def __init__(self):
        self.history = SimpleMemory()
        self.calls = []
        self.response = "sap_faq"

    async def generate_str(self, prompt, params):
        messages = list(self.history.get()) if params.use_history else []
        self.calls.append((messages, prompt))
        return self.response


class TestIntentRoutingContext(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = AgentChatService()
        self.router = RecordingRouter()
        self.service._get_agent_session = AsyncMock(
            return_value=SimpleNamespace(get_llm=AsyncMock(return_value=self.router))
        )
        self.service._execute_skill = AsyncMock(return_value={"content": "test answer"})
        self.histories = {}
        self.service.history_manager.get_chat_history = AsyncMock(
            side_effect=lambda chat_id: ChatHistory(self.histories.get(chat_id, []))
        )
        self.bot = view_models.BotConfig.model_validate({
            "orchestration": {"intent_router": {
                "id": "router", "name": "test", "fallback_skill_id": "basic_qa",
                "llm": {"provider": "test", "model": "test"},
                "prompt_template": "Classify {{query}} using {{skills}}. Explicit new topics override history.",
                "candidate_skills": [
                    {"skill_id": skill, "label": skill}
                    for skill in ["sap_faq", "ops_policy", "basic_qa"]
                ],
            }},
        })

    async def route(self, query, chat_id="chat-a", **kwargs):
        message = view_models.AgentMessage(
            query=query, collections=[],
            completion=view_models.ModelSpec(model="test", model_service_provider="test"),
            **kwargs,
        )
        await self.service.process_agent_message(
            message, "test-user", chat_id, "test-message", SimpleNamespace(put=AsyncMock()),
            bot_config=self.bot,
        )
        return self.service._execute_skill.await_args.args[0]

    def faq_history(self):
        return [
            create_user_message("SAP帐号锁定怎么提流程？", "chat-a", files=[]),
            create_assistant_message("第一步打开UPM；第二步点击链接；第三步输入验证码。", "chat-a"),
        ]

    async def test_followup_receives_previous_question_and_answer(self):
        self.histories["chat-a"] = self.faq_history()
        self.assertEqual(await self.route("第二步是什么意思？"), "sap_faq")
        messages, prompt = self.router.calls[-1]
        self.assertEqual([m["role"] for m in messages], ["user", "assistant"])
        self.assertIn("SAP帐号锁定", messages[0]["content"])
        self.assertIn("第二步点击链接", messages[1]["content"])
        self.assertIn("第二步是什么意思？", prompt)

    async def test_only_last_two_turns_are_forwarded(self):
        recent = self.faq_history() + self.faq_history()
        self.histories["chat-a"] = [create_user_message("OLD_CONTEXT", "chat-a", files=[])] + recent
        await self.route("再解释一下")
        messages, _ = self.router.calls[-1]
        self.assertEqual(len(messages), 4)
        self.assertNotIn("OLD_CONTEXT", str(messages))

    async def test_new_chat_does_not_inherit_cached_router_history(self):
        self.histories["chat-a"] = self.faq_history()
        await self.route("第二步是什么意思？")
        self.router.response = "basic_qa"
        self.assertEqual(await self.route("第二步是什么意思？", "chat-b"), "basic_qa")
        self.assertEqual(self.router.calls[-1][0], [])

    async def test_explicit_topic_change_can_select_another_skill(self):
        self.histories["chat-a"] = self.faq_history()
        self.router.response = "ops_policy"
        self.assertEqual(await self.route("换个话题，查REPORT自测规范。"), "ops_policy")
        self.assertIn("换个话题", self.router.calls[-1][1])
        self.assertEqual(self.service.skill_context_buffers["chat-a"]["skill_id"], "ops_policy")

    async def test_forced_skill_still_bypasses_classifier(self):
        self.assertEqual(await self.route("继续", force_skill_id="ops_policy"), "ops_policy")
        self.assertEqual(self.router.calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
