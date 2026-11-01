import ast
import logging
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_mixed_attachments_keep_the_same_image_numbers_as_visual_observations(monkeypatch):
    config = ModuleType('aperag.config')
    config.settings = SimpleNamespace(dingtalk_image_search_topk=3, dingtalk_image_search_similarity=0.2)
    monkeypatch.setitem(sys.modules, config.__name__, config)
    tree = ast.parse(Path('aperag/service/agent_chat_service.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AgentChatService')
    node = next(n for n in cls.body if getattr(n, 'name', '') == '_execute_image_search')
    node.returns = None
    for arg in node.args.args + node.args.kwonlyargs:
        arg.annotation = None

    async def load(user, chat, document_id):
        return '' if document_id == 'docx' else 'image-bytes:' + document_id

    async def search(**kwargs):
        return [SimpleNamespace(text='matched image', metadata={})]

    async def enrich(user, results):
        return results

    image_service = SimpleNamespace(_load_chat_image_as_data_uri=AsyncMock(side_effect=load),
                                    search_similar_images=AsyncMock(side_effect=search),
                                    _enrich_results_with_faq_chunks=AsyncMock(side_effect=enrich))
    namespace = {'image_search_service': image_service, 'logger': logging.getLogger(__name__)}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'image-search', 'exec'), namespace)
    files = [SimpleNamespace(id='docx', name='context.docx'), SimpleNamespace(id='a', name='a.png'),
             SimpleNamespace(id='b', name='b.png')]
    service = SimpleNamespace(_has_image_files=lambda group: any(f.name.endswith('.png') for f in group))
    result = await namespace['_execute_image_search'](service, 'user', 'chat', files, [object()])
    assert [x.metadata['query_image_position'] for x in result] == [1, 2]
