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

import json
import logging
from collections.abc import Callable
from typing import Any

from mcp_agent.workflows.llm.augmented_llm import RequestParams

from aperag.agent import extract_tool_call_references_from_messages
from aperag.agent.skill_flow_rules import evaluate_condition_node, get_flow_start_node_id
from aperag.llm.llm_error_types import CompletionError
from aperag.schema.skill_flow import ReactFlowEdge, ReactFlowNode
from aperag.schema.view_models import AgentMessage, SkillConfig
from aperag.service.prompt_template_service import build_agent_query_prompt

logger = logging.getLogger(__name__)


async def _execute_action_node(
    *,
    node: ReactFlowNode,
    llm,
    chat_id: str,
    agent_message: AgentMessage,
    user: str,
    request_params: RequestParams,
    query_prompt: str,
    node_results: dict[str, dict[str, Any]],
    build_node_output: Callable[[list[dict[str, Any]]], dict[str, Any]],
) -> dict[str, Any]:
    history_before = llm.history.get() if hasattr(llm.history, "get") else []
    history_before_len = len(history_before)
    node_prompt = node.data.get("prompt") if isinstance(node.data.get("prompt"), str) else ""
    node_label = node.data.get("label") if isinstance(node.data.get("label"), str) else node.id
    context_blocks: list[str] = []
    for source_node_id, result in node_results.items():
        outputs = result.get("outputs", {}) if isinstance(result, dict) else {}
        if outputs:
            context_blocks.append(f"[Node Outputs: {source_node_id}]\n{json.dumps(outputs, ensure_ascii=False)}")

    node_query_prompt = query_prompt
    if node_prompt.strip() or context_blocks:
        extra_parts = []
        if node_prompt.strip():
            extra_parts.append(f"[Current Node: {node_label}]\n{node_prompt.strip()}")
        if context_blocks:
            extra_parts.append("\n\n".join(context_blocks))
        node_query_prompt = "\n\n".join(part for part in [query_prompt, *extra_parts] if part)

    comprehensive_prompt = build_agent_query_prompt(
        chat_id, agent_message=agent_message, user=user, template=node_query_prompt, is_search_confirmed=False
    )
    comprehensive_prompt += (
        '\n\n证据与回答要求：先逐项核对用户的全部问题和条件，再完整作答；精简检索过程说明，'
        '把篇幅留给答案、原文依据和必要限制，不以未展开的标题结束。'
        '不能从局部未检索到推断全文不存在；枚举、跨页续文或条件不足时，'
        '用search_collection(collection_id,query,document_id=已返回的文档ID,page_idx=零基物理页)'
        '核对同文档邻页，Word等无页文档省略page_idx读取全文。context.truncated为真时按next_offset继续。'
        '涉及截图字段、图中表格或图文归属时，用原文已返回的asset_id作为image_asset_ids参数（最多6张）'
        '再次读取上下文以取得实际视觉观察，不能仅凭图片URI或OCR声称已看图。'
        '跨页上方续文不自动归到下方新标题，样例值不能当当前值。'
        '静态代码只证明文本和控制流，不把字符串里的表达式当已验证运行效果。'
        '文本与图片读值冲突时并列呈现，不能用正文或常识把图片标识纠正成另一个值；看不清就标明未知。'
        '物理页码以physical_page为准；page_idx从0开始，页脚印刷页码可能不同。'
        '图片引用复制工具返回的完整asset_url，不省略collection_id和document_id。'
        '得到足够证据后立即完整作答，不反复扩搜同源副本，不要求穷尽全库；'
        '只有具体缺口才补读相应原文或图，不把检索计划当作最终答案。'
        '说明无法从已核验证据确认的部分，不编造缺失步骤或版本审批。'
    )
    response = await llm.generate_str(comprehensive_prompt, request_params)
    finish_reason = getattr(llm, 'last_finish_reason', None)
    if finish_reason in {'length', 'tool_calls', 'function_call'}:
        logger.warning('chat.answer.output_limited', extra={'chat_id': chat_id, 'status': 'continuing'})
        continuation_params = request_params.model_copy(update={
            'tool_filter': {'aperag': set()}, 'max_iterations': 1, 'use_history': True,
        })
        if finish_reason == 'length':
            final_prompt = (
                '上一条回答因输出上限被截断。请从中断位置准确接续，补全未完成的句子和剩余问题，'
                '不要重复已经写出的内容，不再调用工具，不补无依据的事实。'
            )
        else:
            final_prompt = (
                '检索预算已结束。现在只根据已取得的证据完整回答用户全部问题，不再调用工具。'
                '证据不足的具体部分明确说明未确认，不编造，不再只输出检索计划。'
            )
        continuation = await llm.generate_str(final_prompt, continuation_params)
        if getattr(llm, 'last_finish_reason', None) in {'length', 'tool_calls', 'function_call'}:
            raise CompletionError('Model response exceeded its output limit after continuation')
        response = ((response or '') + (continuation or '')) if finish_reason == 'length' else continuation
    if not response:
        raise CompletionError('Model did not return a final answer')
    text = response
    history_after = llm.history.get() if hasattr(llm.history, "get") else []
    current_turn_messages = history_after[history_before_len:]
    references = extract_tool_call_references_from_messages(current_turn_messages)
    outputs = build_node_output(references)
    return {
        "text": text,
        "outputs": outputs,
        "references": references,
    }


async def execute_skill_flow(
    *,
    skill_config: SkillConfig,
    skill_id: str,
    llm,
    chat_id: str,
    agent_message: AgentMessage,
    user: str,
    query_prompt: str,
    effective_system_prompt: str,
    model_name: str,
    max_tokens: int,
    temperature: float,
    build_node_output: Callable[[list[dict[str, Any]]], dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    nodes_by_id = {node.id: node for node in (skill_config.flow.nodes if skill_config.flow else [])}
    outgoing_edges: dict[str, list[ReactFlowEdge]] = {}
    if skill_config.flow:
        for edge in skill_config.flow.edges:
            outgoing_edges.setdefault(edge.source, []).append(edge)

    enabled_tools_from_skill: set[str] = set()
    for binding in skill_config.tools or []:
        if binding.enabled and binding.tool_id:
            enabled_tools_from_skill.add(binding.tool_id)

    if agent_message.files:
        enabled_tools_from_skill.add("search_chat_files")

    current_node_id = get_flow_start_node_id(skill_config)
    if not current_node_id and skill_config.flow and skill_config.flow.nodes:
        current_node_id = skill_config.flow.nodes[0].id

    node_results: dict[str, dict[str, Any]] = {}
    branch_trace: list[str] = []
    final_text = ""
    final_references: list[dict[str, Any]] = []
    visited_node_ids: set[str] = set()
    step_guard = 0

    while current_node_id and current_node_id in nodes_by_id and step_guard < 50:
        step_guard += 1
        if current_node_id in visited_node_ids:
            logger.warning("Detected flow loop at node %s for skill %s", current_node_id, skill_id)
            break
        visited_node_ids.add(current_node_id)

        node = nodes_by_id[current_node_id]
        outgoing = outgoing_edges.get(current_node_id, [])

        if node.type == "action":
            enabled_tools = set(enabled_tools_from_skill)
            node_tools = node.data.get("tools", [])
            if isinstance(node_tools, list):
                enabled_tools.update(str(tool_id) for tool_id in node_tools if tool_id)

            request_params = RequestParams(
                systemPrompt=effective_system_prompt,
                maxTokens=max_tokens,
                model=model_name,
                use_history=True,
                max_iterations=4,
                parallel_tool_calls=True,
                temperature=temperature,
                user=user,
                tool_filter={"aperag": enabled_tools} if enabled_tools else None,
            )

            node_result = await _execute_action_node(
                node=node,
                llm=llm,
                chat_id=chat_id,
                agent_message=agent_message,
                user=user,
                request_params=request_params,
                query_prompt=query_prompt,
                node_results=node_results,
                build_node_output=build_node_output,
            )
            node_results[node.id] = node_result
            final_text = node_result.get("text", final_text)
            final_references = node_result.get("references", final_references)
            next_edge = outgoing[0] if outgoing else None
        elif node.type == "condition":
            decision = evaluate_condition_node(node, node_results)
            branch_trace.append(f"{node.id}:{decision}")
            next_edge = next((edge for edge in outgoing if (edge.sourceHandle or "") == decision), None)
            if not next_edge:
                next_edge = outgoing[0] if outgoing else None
        elif node.type == "startEnd":
            next_edge = outgoing[0] if outgoing else None
            if not next_edge:
                break
        else:
            next_edge = outgoing[0] if outgoing else None

        current_node_id = next_edge.target if next_edge else None

    logger.info(
        "Skill %s flow executed: visited=%s branches=(%s)",
        skill_id,
        ", ".join(sorted(visited_node_ids)) if visited_node_ids else "none",
        ", ".join(branch_trace) if branch_trace else "none",
    )
    return final_text, final_references
