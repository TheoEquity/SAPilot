"""Real document operations and OTel SDK spans; DB/parser/index IO are doubles.

Telemetry startup is replaced to keep this contract suite independent of the
API dependency stack and an external Langfuse collector.
"""

import importlib.util
import sys
import time
from enum import Enum
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def harness(monkeypatch):
    def module(name, **values):
        value = ModuleType(name)
        value.__dict__.update(values)
        monkeypatch.setitem(sys.modules, name, value)
        return value

    def load(name, relative_path):
        spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
        value = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, value)
        spec.loader.exec_module(value)
        return value

    module("aperag.trace", __path__=[])
    settings = SimpleNamespace(
        otel_enabled=True,
        otel_service_name="stage2-test",
        otel_service_version="1.0",
        langfuse_enabled=True,
        langfuse_base_url="http://langfuse:3000",
        langfuse_public_key="test-public",
        langfuse_secret_key="test-secret",
        otel_console_enabled=False,
    )
    module("aperag.config", settings=settings)
    initialized = []

    def initialize(**kwargs):
        initialized.append(kwargs)
        return True

    module("aperag.trace.telemetry", init_telemetry=initialize, is_initialized=lambda: bool(initialized))
    utils = load("aperag.trace.utils", "aperag/trace/utils.py")
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(utils, "get_tracer", provider.get_tracer)
    load("aperag.trace.document", "aperag/trace/document.py")

    class DocumentIndexType(str, Enum):
        VECTOR = "VECTOR"
        FULLTEXT = "FULLTEXT"
        GRAPH = "GRAPH"
        SUMMARY = "SUMMARY"
        VISION = "VISION"

    module("aperag.db.models", DocumentIndexType=DocumentIndexType)
    models = load("aperag.tasks.models", "aperag/tasks/models.py")
    document = SimpleNamespace(id="document-test")
    collection = SimpleNamespace(id="collection-test")
    local_document = SimpleNamespace(path="private-source.txt", is_temp=True)
    task_utils = module(
        "aperag.tasks.utils",
        get_document_and_collection=Mock(return_value=(document, collection)),
        parse_document_content=Mock(return_value=("PRIVATE DOCUMENT CONTENT", [], local_document)),
    )
    index_result = SimpleNamespace(success=True, data={"indexed": True})
    indexer = SimpleNamespace(
        create_index=Mock(return_value=index_result),
        update_index=Mock(return_value=index_result),
        delete_index=Mock(return_value=index_result),
    )
    module("aperag.index.fulltext_index", fulltext_indexer=indexer)
    tasks = load("_stage2_document_under_test", "aperag/tasks/document.py")
    parsed = models.ParsedDocumentData(
        document_id=document.id,
        collection_id=collection.id,
        content="PRIVATE DOCUMENT CONTENT",
        doc_parts=[],
        file_path=local_document.path,
        local_doc_info=models.LocalDocumentInfo(local_document.path, True),
    )
    yield SimpleNamespace(
        task=tasks.DocumentIndexTask(),
        task_utils=task_utils,
        indexer=indexer,
        index_result=index_result,
        settings=settings,
        initialized=initialized,
        exporter=exporter,
        parsed=parsed,
    )
    provider.shutdown()


def assert_span(harness, operation, success, collection=True):
    (span,) = harness.exporter.get_finished_spans()
    assert span.name == f"document.{operation}"
    assert span.attributes["document_id"] == "document-test"
    assert span.attributes["operation"] == operation
    assert span.attributes["success"] is success
    assert span.attributes["task.status"] == ("success" if success else "failed")
    if collection:
        assert span.attributes["collection_id"] == "collection-test"
    assert span.status.status_code is (StatusCode.OK if success else StatusCode.ERROR)
    # Windows' wall clock can resolve both ends of a very short operation to
    # the same tick. A delayed parser below verifies a positive interval.
    assert span.end_time >= span.start_time
    # Neither successful input nor sensitive exception text is exported.
    assert "PRIVATE" not in str(dict(span.attributes))
    assert not span.events
    return span


def test_parse_records_identifiers_and_duration_without_content(harness):
    def parse(*args):
        time.sleep(0.01)
        return harness.task_utils.parse_document_content.return_value

    harness.task_utils.parse_document_content.side_effect = parse
    result = harness.task.parse_document(document_id="document-test")
    assert result == harness.parsed
    span = assert_span(harness, "parse", True)
    assert span.end_time > span.start_time
    assert harness.initialized == [
        {
            "service_name": "stage2-test",
            "service_version": "1.0",
            "langfuse_enabled": True,
            "langfuse_base_url": "http://langfuse:3000",
            "langfuse_public_key": "test-public",
            "langfuse_secret_key": "test-secret",
            "enable_console": False,
        }
    ]


@pytest.mark.parametrize("lookup_failure", [False, True])
def test_parse_exception_is_error_and_preserves_exception(harness, lookup_failure):
    error = ValueError("PRIVATE provider credential or document text")
    target = (
        harness.task_utils.get_document_and_collection if lookup_failure else harness.task_utils.parse_document_content
    )
    target.side_effect = error
    with pytest.raises(ValueError) as caught:
        harness.task.parse_document("document-test")
    assert caught.value is error
    span = assert_span(harness, "parse", False, collection=not lookup_failure)
    assert span.attributes["error.type"] == "ValueError"
    assert span.status.description is None


@pytest.mark.parametrize("operation", ["create", "update", "delete"])
@pytest.mark.parametrize("success", [True, False])
def test_index_business_failure_is_not_span_success(harness, operation, success):
    harness.index_result.success = success
    harness.index_result.error = "PRIVATE backend failure text"
    method = getattr(harness.task, f"{operation}_index")
    kwargs = {"document_id": "document-test", "index_type": "FULLTEXT"}
    if operation != "delete":
        kwargs["parsed_data"] = harness.parsed
    result = method(**kwargs)
    assert result.success is success
    if not success:
        # The existing business result still carries its original error.
        assert "PRIVATE backend failure text" in result.error
    span = assert_span(harness, f"index.{operation}", success)
    assert span.attributes["index_type"] == "FULLTEXT"


@pytest.mark.parametrize("operation", ["create", "update", "delete"])
def test_lookup_exception_is_preserved_for_each_index_operation(harness, operation):
    error = LookupError("PRIVATE missing document")
    harness.task_utils.get_document_and_collection.side_effect = error
    method = getattr(harness.task, f"{operation}_index")
    args = ["document-test", "FULLTEXT"]
    if operation != "delete":
        args.append(harness.parsed)
    with pytest.raises(LookupError) as caught:
        method(*args)
    assert caught.value is error
    assert_span(harness, f"index.{operation}", False, collection=operation != "delete")


def test_worker_telemetry_initializes_once(harness):
    harness.task.parse_document("document-test")
    harness.task.parse_document("document-test")
    assert len(harness.initialized) == 1
    assert len(harness.exporter.get_finished_spans()) == 2


def test_disabled_tracing_preserves_results_without_initializing(harness, caplog):
    import logging

    caplog.set_level(logging.INFO)
    harness.settings.otel_enabled = False
    assert harness.task.parse_document("document-test") == harness.parsed
    harness.index_result.success = False
    harness.index_result.error = "PRIVATE failure"
    result = harness.task.create_index("document-test", "FULLTEXT", harness.parsed)
    assert not result.success
    assert not harness.initialized
    assert not harness.exporter.get_finished_spans()
    records = [r for r in caplog.records if r.msg in ("document.parse.completed", "document.index.create.failed")]
    assert len(records) == 2
    assert all(r.duration_ms >= 0 for r in records)
    # Context is injected at format time, not added as another task identifier.
    failure = next(r for r in caplog.records if r.msg == "document.index.error")
    assert failure.exc_info[0] is Exception
