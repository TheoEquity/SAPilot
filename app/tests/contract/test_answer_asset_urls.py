import ast
import re
from pathlib import Path

import pytest


def resolver():
    path = Path('aperag/agent/tool_reference_extractor.py')
    tree = ast.parse(path.read_text(encoding='utf-8'))
    names = {'_format_reference_content', 'resolve_answer_asset_urls'}
    nodes = [n for n in tree.body if getattr(n, 'name', None) in names]
    assert len(nodes) == 2, 'Final answers have no reference-scoped asset resolver'
    scope = {'re': re}
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), scope)
    return scope['resolve_answer_asset_urls']


def test_bare_answer_image_is_resolved_only_from_its_unique_real_reference():
    refs = [{'text': '![page](asset://page_41.png?mime_type=image/png)',
             'metadata': {'collection_id': 'col', 'document_id': 'doc', 'asset_id': 'page_41.png'}}]
    result = resolver()('![source](asset://page_41.png?mime_type=image/png)', refs)
    assert 'collection_id=col' in result and 'document_id=doc' in result


def test_reused_page_filename_does_not_guess_which_document_image_to_render():
    refs = [{'text': '', 'metadata': {'collection_id': 'col', 'document_id': doc, 'asset_id': 'page_1.png'}}
            for doc in ['docA', 'docB']]
    result = resolver()('![source](asset://page_1.png)', refs)
    assert 'asset://' not in result
    assert '图片来源未确认' in result


def test_already_scoped_image_is_preserved():
    text = '![source](asset://image.png?collection_id=col&document_id=doc)'
    assert resolver()(text, []) == text


@pytest.mark.parametrize('partial', ['document_id=docB', 'collection_id=colB'])
def test_partial_conflicting_scope_cannot_be_combined_with_another_source(partial):
    refs = [{'text': '', 'metadata': {'collection_id': 'colA', 'document_id': 'docA', 'asset_id': 'page.png'}}]
    result = resolver()(f'![source](asset://page.png?{partial})', refs)
    assert 'asset://' not in result
    assert '图片来源未确认' in result


def test_retrieved_source_asset_link_is_rendered_as_an_image():
    refs = [{'text': '', 'metadata': {'collection_id': 'colA', 'document_id': 'docA', 'asset_id': 'page.png'}}]
    source = '[查看原图](asset://page.png?collection_id=colA&document_id=docA)'
    assert resolver()(source, refs) == '!' + source


def test_asset_link_with_conflicting_source_cannot_render_a_wrong_document():
    refs = [{'text': '', 'metadata': {'collection_id': 'colA', 'document_id': 'docA', 'asset_id': 'page.png'}}]
    source = '[查看原图](asset://page.png?collection_id=colB&document_id=docA)'
    actual = resolver()(source, refs)
    assert 'asset://' not in actual and '图片来源未确认' in actual


def test_normal_document_links_are_preserved():
    source = '[材料说明](https://example.test/guide)'
    assert resolver()(source, []) == source


def test_reference_url_scope_cannot_be_relabelled_with_its_metadata_scope():
    refs = [{'text': '![page](asset://page.png?collection_id=colB&document_id=docB)',
             'metadata': {'collection_id': 'colA', 'document_id': 'docA', 'asset_id': 'page.png'}}]
    result = resolver()('[原图](asset://page.png)', refs)
    assert 'asset://' not in result and '图片来源未确认' in result
