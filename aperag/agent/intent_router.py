# Copyright 2025 ApeCloud, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Choose a Skill while leaving chat orchestration and session ownership to the service."""

import logging
import re
from typing import Any, Awaitable, Callable, Optional

from mcp_agent.workflows.llm.augmented_llm import RequestParams, SimpleMemory

from aperag.schema import view_models

logger = logging.getLogger(__name__)


async def route_intent(
    agent_message: view_models.AgentMessage,
    intent_router: view_models.IntentRouterConfig,
    recent_messages: list,
    *,
    user: str,
    chat_id: str,
    resolved_system_prompt: Optional[str],
    get_agent_session: Callable[..., Awaitable[Any]],
) -> str:
    """Route a validated request: forced Skill, first hard rule, then model and fallback."""
    target_skill_id = None

    if agent_message.force_skill_id:
        target_skill_id = agent_message.force_skill_id
        logger.info("Forced skill route: %s -> %s", agent_message.query, target_skill_id)

    # Step 1: Hard rules matching
    if not target_skill_id and intent_router.mode == 'rules+llm' and intent_router.rules:
        # Convert Pydantic models to dicts for try_hard_rules_match
        rules_dict = [rule.model_dump() for rule in intent_router.rules]
        matched = try_hard_rules_match(
            query=agent_message.query,
            rules=rules_dict
        )
        if matched:
            target_skill_id = matched
            logger.info("Hard rule matched: %s -> %s", agent_message.query, target_skill_id)

    # Step 2: LLM intent classification
    if not target_skill_id:
        intent_message = agent_message.model_copy(
            update={
                "completion": agent_message.completion.model_copy(
                    update={
                        "model_service_provider": intent_router.llm.provider,
                        "model": intent_router.llm.model,
                    }
                )
            }
        )
        session = await get_agent_session(intent_message, user, chat_id, resolved_system_prompt)
        llm = await session.get_llm(intent_router.llm.model)

        # Intent router only needs the last 1-2 turns for coreference resolution
        # Take the most recent 4 messages (2 user + 2 assistant) max
        intent_memory = SimpleMemory()
        for msg in recent_messages:
            for openai_msg in msg.to_openai_format(include_tool_results=True):
                intent_memory.append(openai_msg)

        llm.history = intent_memory

        candidate_skills = intent_router.candidate_skills
        skills_desc = "\n".join([
            f"- {s.skill_id}: {s.label or ''} - {s.description or ''}"
            for s in candidate_skills if s.enabled
        ])

        prompt_template = intent_router.prompt_template or ""
        prompt = prompt_template.replace("{{query}}", agent_message.query)
        prompt = prompt.replace("{{skills}}", skills_desc)
        if not prompt.strip():
            prompt = (
                f"Classify into one skill:\n{skills_desc}\n\n"
                f"Query: {agent_message.query}\nReply with skill_id only."
            )

        # Always append the authoritative candidate skill list and exact-output rule.
        # This keeps routing correct even if the saved prompt uses legacy aliases.
        prompt = (
            f"{prompt.strip()}\n\n"
            f"Authoritative candidate skills (you must choose one exact skill_id from this list):\n"
            f"{skills_desc}\n\n"
            f"Current user input:\n{agent_message.query}\n\n"
            f"Output exactly one skill_id from the authoritative candidate list above."
        )

        params = RequestParams(
            maxTokens=intent_router.llm.max_tokens, model=intent_router.llm.model, use_history=False,
            max_iterations=1, temperature=float(intent_router.llm.temperature or 0),
            user=user, tool_filter={"aperag": set()},
        )
        resp = await llm.generate_str(prompt, params)
        classified = (resp or "").strip()

        valid_ids = {s.skill_id for s in candidate_skills if s.enabled}
        if classified in valid_ids:
            target_skill_id = classified
        else:
            target_skill_id = intent_router.fallback_skill_id

        logger.info("Intent classified: %s -> %s", agent_message.query, target_skill_id)

    return target_skill_id


def try_hard_rules_match(
    query: str,
    rules: list,
) -> Optional[str]:
    """Try to match hard rules against the query. Returns target_skill_id or None."""
    def normalize_keyword_text(text: str) -> str:
        normalized = (text or "").lower()
        normalized = re.sub(r"[\s\t\r\n]+", "", normalized)
        normalized = re.sub(r"[!！?？。,.，；;:：~～]", "", normalized)
        normalized = re.sub(r"(查|看|搜|问)一下", r"\1", normalized)
        normalized = re.sub(r"(查|看|搜|问)下", r"\1", normalized)
        return normalized

    normalized_query = normalize_keyword_text(query)

    for rule in rules:
        if not rule.get('enabled', True):
            continue

        rule_type = rule.get('rule_type', 'keyword')
        value = rule.get('value', '')
        target_skill_id = rule.get('target_skill_id', '')

        if not value or not target_skill_id:
            continue

        matched = False
        if rule_type == 'keyword':
            normalized_value = normalize_keyword_text(value)
            matched = (
                value in query
                or value.lower() in query.lower()
                or (normalized_value and normalized_value in normalized_query)
            )
        elif rule_type == 'regex':
            try:
                matched = bool(re.search(value, query, re.IGNORECASE | re.UNICODE))
            except re.error:
                continue

        if matched:
            return target_skill_id

    return None
