"""Exercise the real action boundary with a provider-reported output limit."""
import ast
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def action_boundary():
    tree = ast.parse(Path('aperag/service/agent_chat_service.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AgentChatService')
    node = next(n for n in cls.body if getattr(n, 'name', '') == '_execute_action_node')
    node.returns = None
    for arg in node.args.args + node.args.kwonlyargs:
        arg.annotation = None
    namespace = {
        'build_agent_query_prompt': lambda *a, **k: 'original question',
        'extract_tool_call_references_from_messages': lambda messages: messages,
        'logger': logging.getLogger('test.answer-completion'),
        'CompletionError': RuntimeError,
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'action-boundary', 'exec'), namespace)
    return namespace['_execute_action_node']


class Params:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def model_copy(self, *, update):
        return Params(**{**self.__dict__, **update})


@pytest.mark.asyncio
async def test_provider_length_continues_once_without_repeating_tools_or_losing_prefix():
    llm = SimpleNamespace(last_finish_reason=None, history=SimpleNamespace(get=lambda: []))
    calls = []

    async def generate(prompt, params):
        calls.append((prompt, params))
        llm.last_finish_reason = 'length' if len(calls) == 1 else 'stop'
        return 'field = ma' if len(calls) == 1 else 'tnr.\nComplete answer.'

    llm.generate_str = generate
    original = Params(maxTokens=3072, max_iterations=10, use_history=True, tool_filter={'aperag': {'search_collection'}})
    result = await action_boundary()(
        SimpleNamespace(_build_node_output_from_references=lambda refs: {}),
        node=SimpleNamespace(id='answer', data={}), llm=llm, chat_id='chat',
        agent_message=SimpleNamespace(query='question'), user='user', request_params=original,
        query_prompt='answer all requested parts', node_results={},
    )
    assert len(calls) == 2
    assert result['text'] == 'field = matnr.\nComplete answer.'
    assert calls[1][1].tool_filter == {'aperag': set()}
    assert calls[1][1].max_iterations == 1
    assert original.tool_filter == {'aperag': {'search_collection'}}


@pytest.mark.asyncio
async def test_second_length_is_not_reported_as_a_complete_answer():
    llm = SimpleNamespace(last_finish_reason='length', history=SimpleNamespace(get=lambda: []),
                          generate_str=AsyncMock(return_value='partial'))
    with pytest.raises(RuntimeError, match='output limit'):
        await action_boundary()(
            SimpleNamespace(_build_node_output_from_references=lambda refs: {}),
            node=SimpleNamespace(id='answer', data={}), llm=llm, chat_id='chat',
            agent_message=SimpleNamespace(query='question'), user='user',
            request_params=Params(maxTokens=3072), query_prompt='answer', node_results={},
        )
    assert llm.generate_str.await_count == 2


@pytest.mark.asyncio
async def test_normal_stop_does_not_add_another_model_call():
    llm = SimpleNamespace(last_finish_reason='stop', history=SimpleNamespace(get=lambda: []),
                          generate_str=AsyncMock(return_value='complete'))
    result = await action_boundary()(
        SimpleNamespace(_build_node_output_from_references=lambda refs: {}),
        node=SimpleNamespace(id='answer', data={}), llm=llm, chat_id='chat',
        agent_message=SimpleNamespace(query='question'), user='user', request_params=Params(),
        query_prompt='answer', node_results={},
    )
    assert result['text'] == 'complete'
    assert llm.generate_str.await_count == 1


@pytest.mark.asyncio
async def test_exhausted_tool_budget_still_produces_one_final_answer_without_new_tools():
    llm = SimpleNamespace(last_finish_reason=None, history=SimpleNamespace(get=lambda: []))
    calls = []

    async def generate(prompt, params):
        calls.append(params)
        llm.last_finish_reason = 'tool_calls' if len(calls) == 1 else 'stop'
        return 'I will inspect more evidence.' if len(calls) == 1 else 'Final answer using available evidence.'

    llm.generate_str = generate
    result = await action_boundary()(
        SimpleNamespace(_build_node_output_from_references=lambda refs: {}),
        node=SimpleNamespace(id='answer', data={}), llm=llm, chat_id='chat',
        agent_message=SimpleNamespace(query='question'), user='user', request_params=Params(),
        query_prompt='answer', node_results={},
    )
    assert result['text'] == 'Final answer using available evidence.'
    assert len(calls) == 2 and calls[1].tool_filter == {'aperag': set()}
