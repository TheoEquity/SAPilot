"""Visual evidence uses authorized stored bytes, not caller-supplied URLs."""
import ast
import asyncio
import base64
import copy
import io
import logging
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from PIL import Image


def functions(**overrides):
    path = Path('aperag/service/visual_context_service.py')
    assert path.exists(), 'No authorized visual evidence reader is implemented'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for node in nodes:
        node.decorator_list = []
        node.returns = None
        for arg in node.args.args + node.args.kwonlyargs:
            arg.annotation = None
    namespace = dict(asyncio=asyncio, base64=base64, copy=copy, re=re,
                     logger=logging.getLogger('test.visual'), MAX_IMAGE_BYTES=16 * 1024 * 1024,
                     parseCollectionConfig=lambda config: config,
                     io=io, Image=Image, async_db_ops=SimpleNamespace(query_document_by_id=AsyncMock(return_value=SimpleNamespace(
                         user='user', collection_id='col', status='ACTIVE', gmt_deleted=None))))
    namespace.update(overrides)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


@pytest.mark.asyncio
async def test_foreign_document_cannot_reach_storage_or_model():
    service = SimpleNamespace(get_document_preview=AsyncMock(side_effect=PermissionError('foreign document')),
                              get_document_object=AsyncMock())
    ns = functions(document_service=service)
    with pytest.raises((PermissionError, ValueError)):
        await ns['describe_document_images']('other-user', 'col', 'doc', 'question', ['page_1.png'])
    service.get_document_object.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_or_path_asset_cannot_be_read():
    service = SimpleNamespace(get_document_preview=AsyncMock(return_value=SimpleNamespace(
        markdown_content='![page](asset://page_1.png)', chunks=[])), get_document_object=AsyncMock())
    ns = functions(document_service=service)
    for asset in ['../secret', 'https://example.invalid/private.png', 'other.png']:
        with pytest.raises(ValueError):
            await ns['describe_document_images']('user', 'col', 'doc', 'question', [asset])
    service.get_document_object.assert_not_awaited()


@pytest.mark.asyncio
async def test_source_visual_reader_sends_actual_bytes_in_selected_order():
    async def stream():
        yield b'original-image-bytes'

    service = SimpleNamespace(get_document_preview=AsyncMock(return_value=SimpleNamespace(
        markdown_content='![page](asset://page_1.png)', chunks=[])),
        get_document_object=AsyncMock(return_value=SimpleNamespace(
            headers={'content-type': 'image/png'}, body_iterator=stream())))
    completion = SimpleNamespace(model='vision-model')
    db = SimpleNamespace(query_collection=AsyncMock(return_value=SimpleNamespace(
        config=SimpleNamespace(completion=completion))), query_document_by_id=AsyncMock(return_value=SimpleNamespace(
            user='user', collection_id='col', status='ACTIVE', gmt_deleted=None)))
    ns = functions(document_service=service, async_db_ops=db)
    describe = AsyncMock(return_value='visible field text')
    ns['_describe_images'] = describe
    text = await ns['describe_document_images']('user', 'col', 'doc', 'question', ['page_1.png'])
    assert 'visible field text' in text
    data = describe.await_args.args[2]
    assert base64.b64decode(data[0].split(',', 1)[1]) == b'original-image-bytes'
    service.get_document_object.assert_awaited_once_with('user', 'col', 'doc', 'assets/page_1.png')


@pytest.mark.asyncio
async def test_vision_generation_does_not_mutate_shared_completion_service():
    service = SimpleNamespace(is_vision_model=lambda: True, max_tokens=None,
                              agenerate=AsyncMock(return_value='observations'))
    ns = functions(get_completion_service=Mock(return_value=service))
    spec = SimpleNamespace(model='vl', model_service_provider='approved', custom_llm_provider='openai',
                           temperature=0.1, max_tokens=1024)
    assert await ns['_describe_images']('user', spec, ['data:image/png;base64,YQ=='], 'question') == 'observations'
    assert service.max_tokens is None
    service.agenerate.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('status,deleted', [('DELETED', None), ('ACTIVE', 'deletion-time')])
async def test_deleted_source_document_cannot_reach_preview_storage_or_model(status, deleted):
    async def stream():
        yield b'image'
    service = SimpleNamespace(get_document_preview=AsyncMock(return_value=SimpleNamespace(
        markdown_content='![page](asset://page_1.png)', chunks=[])), get_document_object=AsyncMock(
            return_value=SimpleNamespace(headers={'content-type': 'image/png'}, body_iterator=stream())))
    db = SimpleNamespace(query_document_by_id=AsyncMock(return_value=SimpleNamespace(
        user='user', collection_id='col', status=status, gmt_deleted=deleted)), query_collection=AsyncMock(
            return_value=SimpleNamespace(config=SimpleNamespace(completion=object()))))
    ns = functions(document_service=service, async_db_ops=db)
    ns['_describe_images'] = AsyncMock(return_value='visible')
    with pytest.raises(ValueError, match='accessible'):
        await ns['describe_document_images']('user', 'col', 'doc', 'question', ['page_1.png'])
    service.get_document_preview.assert_not_awaited()
    service.get_document_object.assert_not_awaited()


@pytest.mark.asyncio
async def test_extensionless_source_asset_uses_actual_png_bytes_for_mime():
    stream_data = io.BytesIO()
    Image.new('RGB', (2, 2), 'white').save(stream_data, format='PNG')
    raw = stream_data.getvalue()

    async def stream():
        yield raw

    aid = 'abc123'
    service = SimpleNamespace(get_document_preview=AsyncMock(return_value=SimpleNamespace(
        markdown_content=f'![source](asset://{aid})', chunks=[])), get_document_object=AsyncMock(
            return_value=SimpleNamespace(headers={'content-type': 'application/octet-stream'}, body_iterator=stream())))
    db = SimpleNamespace(query_document_by_id=AsyncMock(return_value=SimpleNamespace(
        user='user', collection_id='col', status='ACTIVE', gmt_deleted=None)), query_collection=AsyncMock(
            return_value=SimpleNamespace(config=SimpleNamespace(completion=object()))))
    ns = functions(document_service=service, async_db_ops=db)
    ns['_describe_images'] = AsyncMock(return_value='actual source observed')
    await ns['describe_document_images']('user', 'col', 'doc', 'question', [aid])
    uri = ns['_describe_images'].await_args.args[2][0]
    assert uri.startswith('data:image/png;base64,')
    assert base64.b64decode(uri.split(',', 1)[1]) == raw
