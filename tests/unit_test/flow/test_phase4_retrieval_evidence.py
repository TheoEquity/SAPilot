import asyncio

import pytest

from aperag.flow.runners.rerank import RerankNodeRunner
from aperag.query.query import DocumentWithScore


def doc(text, score, recall_type):
    return DocumentWithScore(text=text, score=score, metadata={"recall_type": recall_type})


def test_fallback_compares_source_ranks_instead_of_incompatible_scores():
    docs = [
        doc("v2", 0.7, "vector_search"),
        doc("v1", 0.9, "vector_search"),
        doc("f2", 80, "fulltext_search"),
        doc("f1", 120, "fulltext_search"),
    ]
    result = RerankNodeRunner()._apply_fallback_strategy(docs)
    assert [d.text for d in result] == ["v1", "f1", "v2", "f2"]
    assert [d.score for d in result] == [0.9, 120, 0.7, 80]


def test_fallback_keeps_graph_priority_and_single_source_score_order():
    docs = [doc("v2", 0.7, "vector_search"), doc("g", None, "graph_search"), doc("v1", 0.9, "vector_search")]
    assert [d.text for d in RerankNodeRunner()._apply_fallback_strategy(docs)] == ["g", "v1", "v2"]


def mock_api(monkeypatch, payload, status=200):
    from aperag.mcp import server

    calls = []

    class Response:
        status_code = status
        text = "denied" if status != 200 else ""

        def json(self):
            return payload

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            calls.append(("get", url, kwargs))
            return Response()

        async def post(self, url, **kwargs):
            calls.append(("post", url, kwargs))
            return Response()

    monkeypatch.setattr(server, "get_api_key", lambda: "test-token")
    monkeypatch.setattr(server.httpx, "AsyncClient", Client)
    return server.search_collection.fn, calls


def test_mcp_hybrid_limit_retains_topk_per_search_type(monkeypatch):
    items = [
        {"content": f"{kind}{i}", "recall_type": kind, "rank": i}
        for kind in ["fulltext_search", "vector_search"]
        for i in range(1, 4)
    ]
    search, _ = mock_api(monkeypatch, {"query": "q", "items": items})
    result = asyncio.run(search("collection", "q", topk=2))
    assert [x["content"] for x in result["items"]] == [
        "fulltext_search1",
        "fulltext_search2",
        "vector_search1",
        "vector_search2",
    ]
    assert [x["rank"] for x in result["items"]] == [1, 2, 3, 4]


def test_context_exposes_one_based_physical_page_and_resolvable_image_url(monkeypatch):
    search, _ = mock_api(monkeypatch, {
        'doc_filename': 'manual.pdf',
        'markdown_content': '## PDF 第 2 页\n\n![source](asset://page_1.png?mime_type=image/png)',
        'chunks': [{'text': 'split body', 'metadata': {'page_idx': 1, 'asset_id': 'page_1.png', 'chunk_type': 'pdf_page'}}],
    })
    result = asyncio.run(search('collection', 'q', document_id='document', page_idx=1))
    item = result['items'][0]
    assert item['metadata'].get('physical_page') == 2
    assert 'collection_id=collection' in item['metadata'].get('asset_url', '')
    assert 'document_id=document' in item['content']


def test_mcp_accepts_vision_as_the_only_enabled_search_channel(monkeypatch):
    search, calls = mock_api(monkeypatch, {'query': 'screenshot', 'items': []})
    result = asyncio.run(search('collection', 'screenshot', use_vector_index=False,
                               use_fulltext_index=False, use_graph_index=False,
                               use_summary_index=False, use_vision_index=True))
    assert 'error' not in result
    assert calls[0][2]['json']['vision_search']['topk'] == 5


def test_document_page_context_reads_complete_adjacent_pages(monkeypatch):
    markdown = "\n".join(f"## PDF 第 {i + 1} 页\n\npage-{i} complete-body" for i in range(5))
    chunks = [
        {"text": f"split-{i}", "metadata": {"page_idx": i, "asset_id": f"page_{i}.png", "chunk_type": "pdf_page"}}
        for i in range(5)
    ]
    search, calls = mock_api(
        monkeypatch, {"doc_filename": "sample.pdf", "markdown_content": markdown, "chunks": chunks}
    )
    result = asyncio.run(search("collection", "q", document_id="document", page_idx=2))
    assert len(calls) == 1 and calls[0][1].endswith("/collections/collection/documents/document/preview")
    assert calls[0][2]["headers"]["Authorization"] == "Bearer test-token"
    assert [x["metadata"]["page_idx"] for x in result["items"]] == [1, 2, 3]
    assert all("complete-body" in x["content"] and "split-" not in x["content"] for x in result["items"])
    assert result["items"][1]["metadata"]["asset_id"] == "page_2.png"
    assert result["items"][1]["metadata"]["mimetype"] == "image/png"
    assert result["context"]["truncated"] is False


def test_document_context_returns_full_nonpaged_document_and_explicit_continuation(monkeypatch):
    body = "REPORT repeated twice\n" + "x" * 60000 + "\nlast section"
    search, _ = mock_api(monkeypatch, {"doc_filename": "sample.docx", "markdown_content": body, "chunks": []})
    first = asyncio.run(search("collection", "q", document_id="document"))
    assert first["context"]["truncated"] is True
    second = asyncio.run(
        search("collection", "q", document_id="document", context_offset=first["context"]["next_offset"])
    )
    assert second["context"]["truncated"] is False
    assert "".join(x["content"] for x in first["items"] + second["items"]) == body


@pytest.mark.parametrize("status", [401, 403, 404])
def test_document_context_does_not_fallback_after_authorization_failure(monkeypatch, status):
    search, calls = mock_api(monkeypatch, {}, status)
    result = asyncio.run(search("collection", "q", document_id="document", page_idx=2))
    assert "error" in result and len(calls) == 1


@pytest.mark.parametrize(
    "params", [{"page_idx": -1}, {"context_offset": -1}, {"document_id": "../escape"}, {"collection_id": "../escape"}]
)
def test_document_context_rejects_invalid_parameters_before_api(monkeypatch, params):
    search, calls = mock_api(monkeypatch, {})
    kwargs = {"collection_id": "collection", "query": "q", "document_id": "document", **params}
    result = asyncio.run(search(**kwargs))
    assert "error" in result and not calls


@pytest.mark.parametrize("asset_ids", [["../page_0.png"], ["https://outside/x"], ["unknown.png"], ["page_0.png"] * 7])
def test_document_visual_context_rejects_nonpreview_assets(monkeypatch, asset_ids):
    search, _ = mock_api(
        monkeypatch, {"doc_filename": "sample.pdf", "markdown_content": "![page](asset://page_0.png)", "chunks": []}
    )
    result = asyncio.run(search("collection", "q", document_id="document", image_asset_ids=asset_ids))
    assert "error" in result


def test_document_visual_context_is_explicit_and_uses_authenticated_user(monkeypatch):
    import sys
    from types import SimpleNamespace

    from aperag.mcp import server

    seen = []

    async def describe(user_id, collection_id, document_id, query, asset_ids):
        seen.append((user_id, collection_id, document_id, query, asset_ids))
        return "observed image pixels"

    async def api_key_record(key):
        assert key == "test-token"
        return SimpleNamespace(user="verified-user")

    monkeypatch.setitem(
        sys.modules, "aperag.service.visual_context_service", SimpleNamespace(describe_document_images=describe)
    )
    monkeypatch.setattr(server.async_db_ops, "get_api_key_by_key", api_key_record)
    search, _ = mock_api(
        monkeypatch, {"doc_filename": "sample.docx", "markdown_content": "![screenshot](asset://media1)", "chunks": []}
    )
    first = asyncio.run(search("collection", "q", document_id="document"))
    assert not seen and "visual_observations" not in first["context"]
    result = asyncio.run(search("collection", "q", document_id="document", image_asset_ids=["media1"]))
    assert seen == [("verified-user", "collection", "document", "q", ["media1"])]
    assert result["context"]["visual_observations"] == "observed image pixels"


def test_document_context_does_not_substitute_neighbor_for_nonexistent_requested_page(monkeypatch):
    search, _ = mock_api(
        monkeypatch, {"doc_filename": "sample.pdf", "markdown_content": "## PDF 第 1 页\n\nbody", "chunks": []}
    )
    assert "error" in asyncio.run(search("collection", "q", document_id="document", page_idx=1))


def test_pdf_context_labels_leading_solution_with_previous_faq_not_new_heading(monkeypatch):
    pages = [
        '## PDF 第 1 页\n\n7.1. Draft request\nFAQDEMO9001 Draft request\n问题描述：draft',
        '## PDF 第 2 页\n\n解决方案：return draft\n7.2. Approved request\nFAQDEMO9002 Approved request\n问题描述：approved',
        '## PDF 第 3 页\n\n解决方案：execution entry\n7.3. Another request\nFAQDEMO9003 Another request\n问题描述：another',
    ]
    search, _ = mock_api(monkeypatch, {'doc_filename': 'sample.pdf', 'markdown_content': '\n\n'.join(pages), 'chunks': []})
    result = asyncio.run(search('collection', 'q', document_id='document', page_idx=1))
    for item, previous, current, solution in [(result['items'][1], 'FAQDEMO9001', 'FAQDEMO9002', 'return draft'), (result['items'][2], 'FAQDEMO9002', 'FAQDEMO9003', 'execution entry')]:
        sections = item['metadata'].get('faq_context', {}).get('sections', [])
        assert sections and sections[0]['faq_id'] == previous
        assert sections[0]['relation'] == 'continues_previous_page'
        assert sections[1]['faq_id'] == current and sections[1]['relation'] == 'starts_on_page'
        assert item['content'].index('续上页：' + previous) < item['content'].index(solution) < item['content'].index('新条目：' + current)


def test_pdf_faq_context_markers_preserve_raw_source_offsets_and_pagination(monkeypatch):
    pages = ['## PDF 第 1 页\n\n8.1. First\nFAQDEMO9101 First\n问题描述：first', '## PDF 第 2 页\n\n解决方案：continued\n8.2. Second\nFAQDEMO9102 Second\n问题描述：second']
    search, _ = mock_api(monkeypatch, {'doc_filename': 'sample.pdf', 'markdown_content': '\n\n'.join(pages), 'chunks': []})
    result = asyncio.run(search('collection', 'q', document_id='document', page_idx=1))
    item = result['items'][1]
    info = item['metadata'].get('faq_context', {})
    assert info.get('source_characters') == len(pages[1])
    restored = item['content']
    for marker in reversed(info.get('display_markers', [])):
        assert restored[marker['display_start']:marker['display_end']] == marker['text']
        restored = restored[:marker['display_start']] + restored[marker['display_end']:]
    assert restored == pages[1]
    assert result['context']['total_chars'] == len(pages[0]) + 2 + len(pages[1])
    assert result['context']['truncated'] is False and result['context']['next_offset'] is None


@pytest.mark.parametrize('second', [
    '## PDF 第 2 页\n\n解决方案：unknown owner\n### 图片文字识别（可能有误，请核对原页图）\n8.2. OCR only\nFAQDEMO9202 OCR\n问题描述：OCR',
    '## PDF 第 2 页\n\n目录\n8.2. Directory entry\nFAQDEMO9202 ........ 9',
    '## PDF 第 2 页\n\n解决方案：no reliable new section',
])
def test_pdf_context_does_not_infer_faq_boundaries_from_ocr_toc_or_missing_markers(monkeypatch, second):
    first = '## PDF 第 1 页\n\n8.1. First\nFAQDEMO9201 First\n问题描述：first'
    search, _ = mock_api(monkeypatch, {'doc_filename': 'sample.pdf', 'markdown_content': first + '\n\n' + second, 'chunks': []})
    result = asyncio.run(search('collection', 'q', document_id='document', page_idx=1))
    assert result['items'][1]['content'] == second
    assert not result['items'][1]['metadata'].get('faq_context')


def test_pdf_faq_display_markers_do_not_advance_source_pagination(monkeypatch):
    markdown = ('## PDF 第 1 页\n\n9.1. First\nFAQDEMO9301 First\n问题描述：first\n\n'
                '## PDF 第 2 页\n\n解决方案：continued\n9.2. Second\nFAQDEMO9302 Second\n问题描述：' + 'x' * 50000)
    search, _ = mock_api(monkeypatch, {'doc_filename': 'sample.pdf', 'markdown_content': markdown, 'chunks': []})
    first = asyncio.run(search('collection', 'q', document_id='document', page_idx=1))
    assert first['context']['next_offset'] == 48000
    second = asyncio.run(search('collection', 'q', document_id='document', page_idx=1, context_offset=48000))
    assert second['context']['truncated'] is False
    raw_parts = []
    for item in first['items'] + second['items']:
        raw = item['content']
        for marker in reversed(item['metadata'].get('faq_context', {}).get('display_markers', [])):
            raw = raw[:marker['display_start']] + raw[marker['display_end']:]
        raw_parts.append(raw)
    assert ''.join(raw_parts) == markdown
