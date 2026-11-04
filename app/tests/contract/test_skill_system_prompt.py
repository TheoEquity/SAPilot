"""Check the project's LLM wrapper at the SDK boundary without model requests."""

import asyncio
import ast
import copy
import importlib
import inspect
import textwrap
from types import SimpleNamespace
from unittest.mock import patch

from mcp_agent.workflows.llm.augmented_llm import RequestParams, SimpleMemory
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM

from aperag.agent.completion_llm import CompletionAwareOpenAILLM


def sdk_message_assembler():
    """Execute installed SDK assembly, stopping before tool listing/network I/O."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(OpenAIAugmentedLLM.generate)))
    for parent in ast.walk(tree):
        body = getattr(parent, 'body', None)
        if not isinstance(body, list):
            continue
        for index, node in enumerate(body):
            if not (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                    and node.target.id == 'messages'):
                continue
            for end in range(index + 1, len(body)):
                if isinstance(body[end], ast.Expr) and 'OpenAIConverter.convert_mixed_messages_to_openai' in ast.unparse(body[end]):
                    wrapper = ast.parse('def assemble(self, message, request_params, span): pass').body[0]
                    wrapper.body = copy.deepcopy(body[index:end + 1]) + [ast.Return(ast.Name(id='messages', ctx=ast.Load()))]
                    module = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
                    scope = dict(vars(importlib.import_module(OpenAIAugmentedLLM.__module__)))
                    exec(compile(module, 'installed-sdk-message-assembly', 'exec'), scope)
                    return scope['assemble']
    raise AssertionError('Installed SDK message assembly changed; review the integration')


def test_current_prompt_survives_history_and_cached_instruction():
    async def run():
        llm = object.__new__(CompletionAwareOpenAILLM)
        llm.instruction = 'cached-router-instruction'
        llm.history = SimpleMemory()
        llm.history.set([
            {'role': 'system', 'content': 'old-skill'},
            {'role': 'user', 'content': 'previous question'},
            {'role': 'assistant', 'content': 'previous answer'},
        ])
        llm.get_request_params = lambda params: params
        llm._context = SimpleNamespace(tracing_enabled=False)
        captured = []
        assemble = sdk_message_assembler()

        async def sdk_generate(call, message, params):
            messages = assemble(call, message, params, SimpleNamespace(set_attribute=lambda *args: None))
            captured.append((messages, message))
            call.last_finish_reason = 'stop'
            return [SimpleNamespace(content='answer')]

        with patch.object(OpenAIAugmentedLLM, 'generate', sdk_generate):
            for prompt, use_history in [('skill-A', True), ('skill-B', True), ('router', False), ('', True)]:
                await llm.generate('NODE instruction', RequestParams(systemPrompt=prompt, use_history=use_history))
                messages, question = captured[-1]
                systems = [m['content'] for m in messages if m['role'] == 'system']
                assert systems == ([prompt] if prompt else [])
                assert question == 'NODE instruction'
                if use_history:
                    assert any(m.get('content') == 'previous answer' for m in messages)
        assert llm.instruction == 'cached-router-instruction'
        assert llm.last_finish_reason == 'stop'

    asyncio.run(run())
