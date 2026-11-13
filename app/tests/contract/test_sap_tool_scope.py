from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mcp.types import CallToolRequest, CallToolRequestParams, CallToolResult

from aperag.agent.completion_llm import CompletionAwareOpenAILLM
from aperag.agent.sap_scenarios import SkillToolScope, ground_answer
from aperag.agent.tool_reference_extractor import _format_web_read_reference


def test_code_scope_denies_calls_even_if_a_provider_returns_one():
    scope = SkillToolScope(frozenset())
    assert not scope.allows("aperag_search_collection", {"collection_id": "faq"})
    assert not scope.allows("aperag_search_chat_files", {"chat_id": "chat"})
    assert not scope.allows("aperag_web_search", {"query": "x"})


def test_policy_scope_enforces_tool_and_collection_at_call_time():
    scope = SkillToolScope(frozenset({"search_collection"}), frozenset({"policy-a", "policy-b"}))
    assert scope.allows("aperag_search_collection", {"collection_id": "policy-b", "document_id": "doc"})
    assert not scope.allows("aperag_search_collection", {"collection_id": "faq"})
    assert not scope.allows("aperag_search_collection", {})
    assert not scope.allows("aperag_web_search", {"query": "policy"})


@pytest.mark.asyncio
async def test_sdk_never_dispatches_unsolicited_tools_or_out_of_scope_collections():
    llm = CompletionAwareOpenAILLM.__new__(CompletionAwareOpenAILLM)
    llm._context = SimpleNamespace(tracing_enabled=False)
    llm.name = "scope-test"
    call_tool = AsyncMock(return_value=CallToolResult(content=[]))
    llm.agent = SimpleNamespace(call_tool=call_tool)
    code = llm.for_tool_scope(SkillToolScope(frozenset()))
    policy = llm.for_tool_scope(SkillToolScope(frozenset({"search_collection"}), frozenset({"policy"})))
    technical = llm.for_tool_scope(SkillToolScope(frozenset({"search_sap_help"})))

    def request(name: str, arguments: dict) -> CallToolRequest:
        return CallToolRequest(method="tools/call", params=CallToolRequestParams(name=name, arguments=arguments))

    assert (await code.call_tool(request("aperag_search_collection", {"collection_id": "policy"}))).isError
    assert (await code.call_tool(request("aperag_search_sap_help", {"query": "domains"}))).isError
    assert (await policy.call_tool(request("aperag_search_collection", {"collection_id": "faq"}))).isError
    call_tool.assert_not_awaited()
    assert not (await policy.call_tool(request("aperag_search_collection", {"collection_id": "policy"}))).isError
    assert not (await technical.call_tool(request("aperag_search_sap_help", {"query": "domains"}))).isError
    assert call_tool.await_count == 2


def test_unrelated_retrieval_is_not_returned_as_evidence():
    references = [{"text": "A search result about a different policy"}]
    assert ground_answer("[NO_MATCH]\nSome text", references, "missing") == ("missing", [])
    assert ground_answer("[MATCH]\nSome text", [], "missing") == ("missing", [])


def test_grounded_answer_selects_only_the_cited_passages():
    references = [{"evidence_id": "first", "text": "unrelated"}, {"evidence_id": "used", "text": "applicable"}]
    assert ground_answer("[MATCH]\nEVIDENCE: used\nAnswer", references, "missing") == (
        "Answer",
        [{"text": "applicable"}],
    )
    assert ground_answer("[MATCH]\nEVIDENCE: invented\nAnswer", references, "missing") == ("missing", [])


def test_failed_web_reads_cannot_appear_as_sources():
    failed = {"url": "https://example.com/unavailable", "status": "error"}
    retrieved = {"url": "https://example.com/content", "status": "success", "content": "Source text"}
    assert _format_web_read_reference({"results": [failed]}, {}) is None
    reference = _format_web_read_reference({"results": [failed, retrieved]}, {})
    assert reference["metadata"]["urls"] == [retrieved["url"]]
    assert "Source text" in reference["text"]
