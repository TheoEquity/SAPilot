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

"""
Unit tests for image search refactoring in AgentChatService.

Tests cover:
1. `_execute_image_search` - returns List[DocumentWithScore] with proper metadata
2. `_build_image_search_standard_references` - returns references with correct format
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aperag.query.query import DocumentWithScore
from aperag.schema import view_models
from aperag.service.agent_chat_service import AgentChatService


class MockSettings:
    """Mock settings object with required attributes."""
    dingtalk_image_search_topk = 5
    dingtalk_image_search_similarity = 0.7
    dingtalk_image_search_confirmed_similarity = 0.8


def setup_mock_settings():
    """Create a mock aperag.core.config.settings module for testing."""
    mock_config = MagicMock()
    mock_config.settings = MockSettings()
    
    mock_core = MagicMock()
    mock_core.config = mock_config
    
    sys.modules['aperag.core'] = mock_core
    sys.modules['aperag.core.config'] = mock_config


class TestExecuteImageSearch:
    """Tests for _execute_image_search method."""

    @pytest.fixture
    def service(self):
        return AgentChatService(session=None)

    @pytest.fixture
    def mock_file(self):
        file = MagicMock(spec=view_models.File)
        file.id = "test-file-id-001"
        return file

    @pytest.fixture
    def mock_collection(self):
        collection = MagicMock(spec=view_models.Collection)
        collection.id = "test-collection-id-001"
        collection.title = "Test Collection"
        collection.config = MagicMock()
        return collection

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_files(self, service, mock_collection):
        setup_mock_settings()
        result = await service._execute_image_search(
            user="test-user",
            chat_id="test-chat-id",
            files=[],
            collections=[mock_collection],
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_collections(self, service, mock_file):
        setup_mock_settings()
        result = await service._execute_image_search(
            user="test-user",
            chat_id="test-chat-id",
            files=[mock_file],
            collections=[],
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_files_is_none(self, service, mock_collection):
        setup_mock_settings()
        result = await service._execute_image_search(
            user="test-user",
            chat_id="test-chat-id",
            files=None,
            collections=[mock_collection],
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_collections_is_none(self, service, mock_file):
        setup_mock_settings()
        result = await service._execute_image_search(
            user="test-user",
            chat_id="test-chat-id",
            files=[mock_file],
            collections=None,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_enriched_results_with_faq_chunks(self, service, mock_file, mock_collection):
        setup_mock_settings()
        
        mock_image_data_uri = "data:image/png;base64,fakebase64data"
        mock_search_result = DocumentWithScore(
            text="Original image search result text",
            score=0.85,
            metadata={
                "collection_id": "coll-001",
                "document_id": "doc-001",
                "asset_id": "asset-001",
                "faq_id": "faq-12345",
                "chunk_type": "image_chunk",
                "source": "test_source",
                "collection_title": "Test Collection",
            },
        )
        mock_enriched_result = DocumentWithScore(
            text="Enriched FAQ content from chunk",
            score=0.85,
            metadata={
                "collection_id": "coll-001",
                "document_id": "doc-001",
                "asset_id": "asset-001",
                "faq_id": "faq-12345",
                "chunk_type": "faq_entry",
                "source": "test_source",
                "collection_title": "Test Collection",
            },
        )

        with patch(
            "aperag.service.agent_chat_service.image_search_service"
        ) as mock_image_search_service:
            mock_image_search_service._load_chat_image_as_data_uri = AsyncMock(
                return_value=mock_image_data_uri
            )
            mock_image_search_service.search_similar_images = AsyncMock(
                return_value=[mock_search_result]
            )
            mock_image_search_service._enrich_results_with_faq_chunks = AsyncMock(
                return_value=[mock_enriched_result]
            )

            result = await service._execute_image_search(
                user="test-user",
                chat_id="test-chat-id",
                files=[mock_file],
                collections=[mock_collection],
            )

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], DocumentWithScore)
        assert result[0].text == "Enriched FAQ content from chunk"
        assert result[0].score == 0.85
        assert result[0].metadata["collection_id"] == "coll-001"
        assert result[0].metadata["document_id"] == "doc-001"
        assert result[0].metadata["asset_id"] == "asset-001"
        assert result[0].metadata["faq_id"] == "faq-12345"
        assert result[0].metadata["chunk_type"] == "faq_entry"

    @pytest.mark.asyncio
    async def test_returns_empty_when_image_load_fails(self, service, mock_file, mock_collection):
        setup_mock_settings()
        
        with patch(
            "aperag.service.agent_chat_service.image_search_service"
        ) as mock_image_search_service:
            mock_image_search_service._load_chat_image_as_data_uri = AsyncMock(
                return_value=None
            )

            result = await service._execute_image_search(
                user="test-user",
                chat_id="test-chat-id",
                files=[mock_file],
                collections=[mock_collection],
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_search_returns_no_results(self, service, mock_file, mock_collection):
        setup_mock_settings()
        
        mock_image_data_uri = "data:image/png;base64,fakebase64data"

        with patch(
            "aperag.service.agent_chat_service.image_search_service"
        ) as mock_image_search_service:
            mock_image_search_service._load_chat_image_as_data_uri = AsyncMock(
                return_value=mock_image_data_uri
            )
            mock_image_search_service.search_similar_images = AsyncMock(
                return_value=[]
            )

            result = await service._execute_image_search(
                user="test-user",
                chat_id="test-chat-id",
                files=[mock_file],
                collections=[mock_collection],
            )

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_search_exception_gracefully(self, service, mock_file, mock_collection):
        setup_mock_settings()
        
        with patch(
            "aperag.service.agent_chat_service.image_search_service"
        ) as mock_image_search_service:
            mock_image_search_service._load_chat_image_as_data_uri = AsyncMock(
                side_effect=Exception("Network error")
            )

            result = await service._execute_image_search(
                user="test-user",
                chat_id="test-chat-id",
                files=[mock_file],
                collections=[mock_collection],
            )

        assert result == []


class TestBuildImageSearchStandardReferences:
    """Tests for _build_image_search_standard_references method."""

    @pytest.fixture
    def service(self):
        return AgentChatService(session=None)

    def test_returns_empty_when_no_results(self, service):
        result = service._build_image_search_standard_references([])
        assert result == []

    def test_returns_empty_when_none(self, service):
        result = service._build_image_search_standard_references(None)
        assert result == []

    def test_creates_reference_with_correct_format(self, service):
        mock_result = DocumentWithScore(
            text="FAQ answer content",
            score=0.92,
            metadata={
                "collection_id": "coll-001",
                "document_id": "doc-001",
                "asset_id": "asset-001",
                "faq_id": "faq-12345",
                "chunk_type": "faq_entry",
                "source": "sap_faq_docs",
                "collection_title": "SAP FAQ Collection",
            },
        )

        result = service._build_image_search_standard_references([mock_result])

        assert isinstance(result, list)
        assert len(result) == 1

        ref = result[0]
        assert "text" in ref
        assert "metadata" in ref
        assert "score" in ref

        assert ref["text"] == "FAQ answer content"
        assert ref["score"] == 0.92

        metadata = ref["metadata"]
        assert metadata["type"] == "search_collection"
        assert metadata["collection_id"] == "coll-001"
        assert metadata["document_id"] == "doc-001"
        assert metadata["asset_id"] == "asset-001"
        assert metadata["recall_type"] == "vision_search"
        assert metadata["chunk_type"] == "faq_entry"
        assert metadata["faq_id"] == "faq-12345"
        assert metadata["document_source"] == "sap_faq_docs"
        assert metadata["rank"] == 1
        assert metadata["result_count"] == 1

    def test_uses_first_result_as_main_reference(self, service):
        results = [
            DocumentWithScore(
                text="First result - best match",
                score=0.95,
                metadata={
                    "collection_id": "coll-001",
                    "document_id": "doc-001",
                    "asset_id": "asset-001",
                    "chunk_type": "faq_entry",
                },
            ),
            DocumentWithScore(
                text="Second result",
                score=0.80,
                metadata={
                    "collection_id": "coll-002",
                    "document_id": "doc-002",
                    "asset_id": "asset-002",
                    "chunk_type": "faq_entry",
                },
            ),
        ]

        result = service._build_image_search_standard_references(results)

        assert len(result) == 1
        assert result[0]["text"] == "First result - best match"
        assert result[0]["score"] == 0.95
        assert result[0]["metadata"]["collection_id"] == "coll-001"
        assert result[0]["metadata"]["result_count"] == 2

    def test_defaults_chunk_type_to_faq_entry_when_missing(self, service):
        mock_result = DocumentWithScore(
            text="FAQ content",
            score=0.88,
            metadata={
                "collection_id": "coll-001",
                "document_id": "doc-001",
                "asset_id": "asset-001",
            },
        )

        result = service._build_image_search_standard_references([mock_result])

        assert result[0]["metadata"]["chunk_type"] == "faq_entry"

    def test_handles_none_metadata(self, service):
        mock_result = DocumentWithScore(
            text="Result with no metadata",
            score=0.75,
            metadata=None,
        )

        result = service._build_image_search_standard_references([mock_result])

        assert len(result) == 1
        assert result[0]["text"] == "Result with no metadata"
        assert result[0]["score"] == 0.75
        assert result[0]["metadata"]["type"] == "search_collection"
        assert result[0]["metadata"]["recall_type"] == "vision_search"
        assert result[0]["metadata"]["chunk_type"] == "faq_entry"
        assert result[0]["metadata"]["collection_id"] is None
        assert result[0]["metadata"]["document_id"] is None
        assert result[0]["metadata"]["asset_id"] is None

    def test_handles_none_score(self, service):
        mock_result = DocumentWithScore(
            text="Result without score",
            score=None,
            metadata={
                "collection_id": "coll-001",
                "document_id": "doc-001",
                "asset_id": "asset-001",
                "chunk_type": "faq_entry",
            },
        )

        result = service._build_image_search_standard_references([mock_result])

        assert result[0]["score"] == 1.0

    def test_includes_all_metadata_fields_from_original(self, service):
        mock_result = DocumentWithScore(
            text="Rich metadata result",
            score=0.90,
            metadata={
                "collection_id": "coll-001",
                "document_id": "doc-001",
                "asset_id": "asset-001",
                "faq_id": "faq-99999",
                "chunk_type": "faq_entry",
                "source": "original_source",
                "collection_title": "My Collection",
                "extra_field": "extra_value",
            },
        )

        result = service._build_image_search_standard_references([mock_result])

        metadata = result[0]["metadata"]
        assert metadata["type"] == "search_collection"
        assert metadata["collection_id"] == "coll-001"
        assert metadata["document_id"] == "doc-001"
        assert metadata["asset_id"] == "asset-001"
        assert metadata["recall_type"] == "vision_search"
        assert metadata["chunk_type"] == "faq_entry"
        assert metadata["faq_id"] == "faq-99999"
        assert metadata["document_source"] == "original_source"
        assert metadata["rank"] == 1
        assert metadata["result_count"] == 1
        assert metadata["extra_field"] == "extra_value"
        assert metadata["collection_title"] == "My Collection"


class TestBuildImageSearchTextQuery:
    """Tests for image-search-to-text query handoff."""

    @pytest.fixture
    def service(self):
        return AgentChatService(session=None)

    def test_builds_query_that_requires_text_search(self, service):
        result = service._build_image_search_text_query(
            original_query="怎么回事",
            question_text="不允许负值总计金额",
        )

        assert "检索关键词：不允许负值总计金额" in result
        assert "用户原始问题：怎么回事" in result
        assert "调用 search_collection 检索运维FAQ知识库" in result

    def test_does_not_treat_image_hit_as_final_answer_context(self, service):
        result = service._build_image_search_text_query(
            original_query="帮我看下截图",
            question_text="预算冻结时报错",
        )

        assert "候选" not in result
        assert "主依据" not in result
        assert "按 FAQ 标准回答格式输出" not in result


class TestConfirmedImageSearchHit:
    """Tests for image search confirmed-hit threshold."""

    @pytest.fixture
    def service(self):
        return AgentChatService(session=None)

    def test_accepts_hit_at_confirmed_threshold(self, service):
        result = DocumentWithScore(text="FAQ content", score=0.8, metadata={})

        assert service._is_confirmed_image_search_hit(result) is True

    def test_rejects_hit_below_confirmed_threshold(self, service):
        result = DocumentWithScore(text="FAQ content", score=0.79, metadata={})

        assert service._is_confirmed_image_search_hit(result) is False

    def test_rejects_hit_without_numeric_score(self, service):
        result = DocumentWithScore(text="FAQ content", score=None, metadata={})

        assert service._is_confirmed_image_search_hit(result) is False


class TestImageSearchNoMatchResponse:
    """Tests for image-search no-match guardrail helpers."""

    @pytest.fixture
    def service(self):
        return AgentChatService(session=None)

    def test_detects_image_files(self, service):
        image_file = MagicMock(spec=view_models.File)
        image_file.name = "screenshot.PNG"
        text_file = MagicMock(spec=view_models.File)
        text_file.name = "notes.txt"

        assert service._has_image_files([text_file, image_file]) is True

    def test_ignores_non_image_files(self, service):
        text_file = MagicMock(spec=view_models.File)
        text_file.name = "notes.txt"

        assert service._has_image_files([text_file]) is False

    def test_builds_chinese_unmatched_image_response(self, service):
        response = service._build_unmatched_image_response("zh-CN")

        assert "未匹配到知识库中的明确图片" in response
        assert "文字描述" in response

    def test_builds_english_unmatched_image_response(self, service):
        response = service._build_unmatched_image_response("en-US")

        assert "could not find a clear matching image" in response
        assert "describe the issue in text" in response

    def test_continues_unmatched_image_prompt_for_short_follow_up(self, service):
        history_message = MagicMock()
        history_message.role = "assistant"
        history_message.content = service._build_unmatched_image_response("zh-CN")

        result = service._should_continue_unmatched_image_prompt("怎么办", [history_message])

        assert result is True

    def test_allows_specific_follow_up_after_unmatched_image_prompt(self, service):
        history_message = MagicMock()
        history_message.role = "assistant"
        history_message.content = service._build_unmatched_image_response("zh-CN")

        result = service._should_continue_unmatched_image_prompt("报错提示总计金额为负", [history_message])

        assert result is False

    def test_allows_short_follow_up_without_unmatched_image_prompt(self, service):
        history_message = MagicMock()
        history_message.role = "assistant"
        history_message.content = "这是一个正常 FAQ 回答"

        result = service._should_continue_unmatched_image_prompt("怎么办", [history_message])

        assert result is False
