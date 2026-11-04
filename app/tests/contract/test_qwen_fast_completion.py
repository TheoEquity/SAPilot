import ast
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


def completion_service():
    tree = ast.parse(Path('aperag/llm/completion/completion_service.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CompletionService')
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='visible text'))])
    provider = SimpleNamespace(acompletion=AsyncMock(return_value=response), completion=Mock(return_value=response))
    scope = {'litellm': provider, 'logger': logging.getLogger(__name__), 'CompletionError': RuntimeError,
             'InvalidPromptError': ValueError, 'wrap_litellm_error': lambda *a: RuntimeError('provider failed')}
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), cls], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), 'completion-service', 'exec'), scope)
    return scope['CompletionService'], provider


@pytest.mark.asyncio
async def test_qwen_flash_image_extraction_requests_direct_answer_in_sync_and_async_paths():
    cls, provider = completion_service()
    svc = cls('openai', 'qwen3.8-flash', 'https://approved.invalid', 'test-key', vision=True)
    assert svc.generate([], 'Read visible text', images=['data:image/png;base64,YQ==']) == 'visible text'
    assert await svc.agenerate([], 'Read visible text', images=['data:image/png;base64,YQ==']) == 'visible text'
    for call in [provider.completion.call_args, provider.acompletion.await_args]:
        assert call.kwargs.get('extra_body') == {'enable_thinking': False}


def test_other_model_request_options_are_unchanged():
    cls, provider = completion_service()
    cls('openai', 'other-model', 'https://approved.invalid', 'test-key').generate([], 'question')
    assert 'extra_body' not in provider.completion.call_args.kwargs


@pytest.mark.asyncio
async def test_sdk_qwen_request_is_fast_without_mutating_explicit_request_metadata():
    class Base:
        async def generate(self, message, params):
            return params

        def _reasoning(self, model):
            return False

    class Params:
        model = 'qwen3.8-flash'
        temperature = 0.1
        metadata = {'extra_body': {'other_option': 'preserved'}}

        def model_copy(self, *, update):
            result = Params()
            result.__dict__.update(update)
            return result

    tree = ast.parse(Path('aperag/agent/completion_llm.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    scope = {'OpenAIAugmentedLLM': Base}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), 'completion-llm', 'exec'), scope)
    params = Params()
    used = await scope['CompletionAwareOpenAILLM']().generate('question', params)
    assert used.metadata['extra_body'] == {'other_option': 'preserved', 'enable_thinking': False}
    assert params.metadata == {'extra_body': {'other_option': 'preserved'}}
    assert used.metadata.get('temperature') == 0.1


@pytest.mark.asyncio
async def test_sdk_publishes_only_final_answer_instead_of_tool_planning_messages():
    class Base:
        async def generate(self, message, params):
            return [SimpleNamespace(content='I need to search first.'), SimpleNamespace(content='Evidence-based answer.')]

    tree = ast.parse(Path('aperag/agent/completion_llm.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    scope = {'OpenAIAugmentedLLM': Base}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), 'completion-llm', 'exec'), scope)
    llm = scope['CompletionAwareOpenAILLM']()
    assert await llm.generate_str('question') == 'Evidence-based answer.'
