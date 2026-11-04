import asyncio
import io
import json
import logging

import pytest

from aperag.logging import JsonFormatter, RequestLoggingMiddleware, SafeStreamHandler, log_context, log_stage


def capture():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter(service="test"))
    logger = logging.getLogger("test.application-logging")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    return logger, stream


def test_fields_and_exception_chain_without_private_text():
    logger, stream = capture()
    with log_context(document_id="doc-test"):
        try:
            try:
                raise FileNotFoundError("PRIVATE document token=secret")
            except FileNotFoundError as cause:
                raise RuntimeError("PRIVATE provider response") from cause
        except RuntimeError:
            logger.exception("document.parse.failed", extra={"body": "PRIVATE", "status": "failed"})
    value = json.loads(stream.getvalue())
    assert value["document_id"] == "doc-test"
    assert [e["type"] for e in value["error_chain"]] == ["RuntimeError", "FileNotFoundError"]
    assert value["error_chain"][0]["frames"]
    assert "PRIVATE" not in stream.getvalue()
    assert "secret" not in stream.getvalue()
    # Legacy free-form messages can contain source content; do not serialize them.
    stream.seek(0); stream.truncate()
    logger.info("PRIVATE document content: %s", "secret")
    assert "PRIVATE" not in stream.getvalue()
    assert "secret" not in stream.getvalue()


@pytest.mark.asyncio
async def test_context_isolation_and_reset():
    logger, stream = capture()

    async def work(document_id):
        with log_context(document_id=document_id):
            await asyncio.sleep(0)
            logger.info("document.done")

    await asyncio.gather(work("doc-a"), work("doc-b"))
    logger.info("outside")
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert [r.get("document_id") for r in records] == ["doc-a", "doc-b", None]


def test_stage_logs_failure_and_preserves_exception(caplog):
    error = ValueError("PRIVATE input")
    with pytest.raises(ValueError) as caught:
        with log_stage("document.convert", document_id="doc-test"):
            raise error
    assert caught.value is error
    records = [r for r in caplog.records if r.msg == "document.convert.failed"]
    assert records and records[-1].status == "failed"
    assert records[-1].duration_ms >= 0


@pytest.mark.asyncio
async def test_http_logging_preserves_stream_and_does_not_log_query(caplog):
    sent = []

    async def app(scope, receive, send):
        scope["route"] = type("Route", (), {"path": "/documents/{document_id}"})()
        scope["path_params"] = {"document_id": "doc-test"}
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"PRIVATE", "more_body": True})
        await send({"type": "http.response.body", "body": b" final"})

    with caplog.at_level(logging.INFO):
        await RequestLoggingMiddleware(app)(
            {"type": "http", "method": "POST", "query_string": b"token=PRIVATE"},
            None, lambda m: _append(sent, m),
        )
    assert sent[1]["body"] == b"PRIVATE" and sent[1]["more_body"] is True
    record = next(r for r in caplog.records if r.msg == "http.request.completed")
    value = JsonFormatter(service="api").format(record)
    assert "PRIVATE" not in value
    assert json.loads(value)["document_id"] == "doc-test"


async def _append(items, value):
    items.append(value)


def test_log_output_failure_does_not_raise_or_print_private_record(capsys):
    class BrokenStream:
        def write(self, value):
            raise OSError("disk unavailable")

    handler = SafeStreamHandler(BrokenStream())
    handler.setFormatter(JsonFormatter())
    handler.handle(logging.LogRecord("test", logging.ERROR, __file__, 1, "PRIVATE", (), None))
    assert capsys.readouterr().err == ""


@pytest.mark.asyncio
async def test_existing_trace_returned_without_creating_new_id():
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    sent = []

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 204, "headers": []})

    with provider.get_tracer("logging-test").start_as_current_span("request") as span:
        await RequestLoggingMiddleware(app)({"type": "http", "method": "POST"}, None, lambda m: _append(sent, m))
        assert dict(sent[0]["headers"])[b"x-trace-id"].decode() == format(span.get_span_context().trace_id, "032x")
    assert not trace.get_current_span().get_span_context().is_valid
    sent.clear()
    await RequestLoggingMiddleware(app)({"type": "http", "method": "POST"}, None, lambda m: _append(sent, m))
    assert b"x-trace-id" not in dict(sent[0]["headers"])
    provider.shutdown()


@pytest.mark.asyncio
async def test_http_cancellation_is_not_system_failure(caplog):
    async def app(scope, receive, send):
        raise asyncio.CancelledError()

    with caplog.at_level(logging.INFO), pytest.raises(asyncio.CancelledError):
        await RequestLoggingMiddleware(app)({"type": "http", "method": "POST"}, None, None)
    record = next(r for r in caplog.records if r.msg == "http.request.cancelled")
    assert record.levelno == logging.INFO and record.status == "cancelled"


def test_returned_failure_is_logged_as_failure(caplog):
    with log_stage("document.index", document_id="doc-test") as outcome:
        outcome.update(status="failed", error_type="IndexTaskError")
    record = next(r for r in caplog.records if r.msg == "document.index.failed")
    assert record.status == "failed" and record.error_type == "IndexTaskError"


def test_document_retry_hooks_keep_existing_task_and_business_ids(caplog):
    import ast
    from pathlib import Path
    from types import SimpleNamespace

    tree = ast.parse(Path("config/celery_tasks.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "BaseIndexTask")

    class Task:
        def on_retry(self, *args):
            return "retry-parent"

        def on_failure(self, *args):
            return "failure-parent"

    namespace = {"Task": Task, "List": list, "logger": logging.getLogger("test.worker-hooks"), "logging": logging}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "config/celery_tasks.py", "exec"), namespace)
    task = namespace["BaseIndexTask"]()
    task.request = SimpleNamespace(retries=2)
    with caplog.at_level(logging.WARNING):
        assert task.on_retry(ValueError("PRIVATE"), "existing-task", ["doc-test"], {}, None) == "retry-parent"
        assert task.on_failure(ValueError("PRIVATE"), "existing-task", [], {"document_id": "doc-test"}, None) == "failure-parent"
    assert [r.msg for r in caplog.records] == ["document.task.retrying", "document.task.failed"]
    assert all(r.document_id == "doc-test" and r.task_id == "existing-task" and r.retry_count == 2 for r in caplog.records)
    assert "PRIVATE" not in "".join(JsonFormatter().format(r) for r in caplog.records)


def test_file_output_uses_shared_directory_and_bounded_rotation(tmp_path, monkeypatch):
    from aperag import logging as application_logging

    monkeypatch.setattr(application_logging, "log_settings", lambda: {
        "directory": tmp_path, "max_bytes": 700, "backup_count": 2,
    })
    handler = application_logging.file_handler("api")
    try:
        for _ in range(20):
            handler.handle(logging.LogRecord("test", logging.INFO, __file__, 1, "http.request.completed", (), None))
    finally:
        handler.close()
    files = sorted(tmp_path.iterdir())
    assert {f.name for f in files} == {"api.log", "api.log.1", "api.log.2"}
    assert all(f.stat().st_size <= 700 for f in files)
    assert all(json.loads(line)["service"] == "api" for f in files for line in f.read_text().splitlines())


def test_log_directory_override_is_independent_of_current_directory(tmp_path, monkeypatch):
    from aperag.logging import log_settings

    monkeypatch.setenv("SAPILOT_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.chdir(tmp_path)
    assert log_settings()["directory"] == tmp_path / "logs"
