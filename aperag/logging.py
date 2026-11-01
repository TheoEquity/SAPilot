"""Small shared logging configuration, safe fields and operation context."""

import asyncio
import json
import logging
import math
import os
import re
import time
import traceback
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

_context = ContextVar("log_context", default={})
_fields = {
    "document_id",
    "collection_id",
    "message_id",
    "chat_id",
    "trace_id",
    "index_type",
    "stage",
    "status",
    "duration_ms",
    "status_code",
    "method",
    "path",
    "error_code",
    "error_type",
    "dependency",
    "page_count",
    "image_count",
    "chunk_count",
    "retry_count",
    "task_id",
}
_identifier = re.compile(r"^[a-zA-Z0-9_.:-]{1,128}$")
_event = re.compile(r"^[a-z][a-z0-9_.]{0,100}$")


def log_settings():
    root = Path(__file__).resolve().parents[1]
    settings = json.loads((root / "config/logging/settings.json").read_text(encoding="utf-8"))
    directory = Path(os.environ.get("SAPILOT_LOG_DIR") or settings["directory"])
    settings["directory"] = directory if directory.is_absolute() else root / directory
    return settings


def file_handler(service):
    settings = log_settings()
    directory = settings["directory"]
    directory.mkdir(parents=True, exist_ok=True)
    handler = SafeRotatingFileHandler(
        directory / f"{service}.log",
        maxBytes=settings["max_bytes"],
        backupCount=settings["backup_count"],
        encoding="utf-8",
        delay=True,
    )
    handler.setFormatter(JsonFormatter(service=service))
    return handler


def current_trace_id():
    try:
        from opentelemetry import trace

        context = trace.get_current_span().get_span_context()
        return format(context.trace_id, "032x") if context.is_valid else None
    except Exception:
        return None


@contextmanager
def log_context(**fields):
    token = _context.set({**_context.get(), **fields})
    try:
        yield
    finally:
        _context.reset(token)


def _error_chain(error):
    result, seen = [], set()
    while error is not None and id(error) not in seen and len(result) < 8:
        seen.add(id(error))
        frames = [
            {"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
            for f in traceback.extract_tb(error.__traceback__)[-12:]
        ]
        entry = {"type": type(error).__name__, "frames": frames}
        # Safe finite classification; never emit the exception message/arguments.
        message = str(error)
        for dependency in ("soffice", "tesseract"):
            if message == f"{dependency} command not found" or message.startswith(
                f"PDF screenshot extraction requires {dependency}"
            ):
                entry["dependency"] = dependency
        result.append(entry)
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    return result


class JsonFormatter(logging.Formatter):
    def __init__(self, service="api"):
        super().__init__()
        self.service = service

    def format(self, record):
        result = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "event": record.msg if isinstance(record.msg, str) and _event.fullmatch(record.msg) else "application.log",
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }
        data = {**_context.get(), **record.__dict__}
        trace_id = data.get("trace_id") or current_trace_id()
        if trace_id:
            data["trace_id"] = trace_id
        for key in _fields:
            value = data.get(key)
            if isinstance(value, (int, float, bool)) and math.isfinite(value):
                result[key] = value
            elif isinstance(value, str):
                if key == "path":
                    result[key] = value.split("?", 1)[0][:200]
                elif key == "trace_id":
                    if re.fullmatch(r"[a-fA-F0-9]{32}", value):
                        result[key] = value
                elif _identifier.fullmatch(value):
                    result[key] = value
        if record.exc_info and record.exc_info[1] is not None:
            result["error_type"] = type(record.exc_info[1]).__name__
            result["error_chain"] = _error_chain(record.exc_info[1])
        # Deliberately omit legacy free-form messages, args and arbitrary extra:
        # Celery result reprs and HTTP/LLM errors can contain entire private inputs.
        return json.dumps(result, ensure_ascii=False)


class SafeStreamHandler(logging.StreamHandler):
    def handleError(self, record):
        # logging's default diagnostic prints the original record and its args.
        pass


class SafeRotatingFileHandler(RotatingFileHandler):
    def handleError(self, record):
        pass


def logging_config(service):
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"json": {"()": "aperag.logging.JsonFormatter", "service": service}},
        "handlers": {
            "console": {"class": "aperag.logging.SafeStreamHandler", "formatter": "json"},
            "file": {"()": "aperag.logging.file_handler", "service": service},
        },
        "root": {"level": "INFO", "handlers": ["console", "file"]},
        "loggers": {
            name: {"handlers": [], "propagate": True, "level": level}
            for name, level in [("aperag", "INFO"), ("celery", "INFO"), ("celery.task", "INFO"), ("LiteLLM", "WARNING")]
        },
    }


@contextmanager
def log_stage(event, **fields):
    logger = logging.getLogger("aperag.operations")
    started = time.perf_counter()
    outcome = {"status": "success"}
    with log_context(**fields):
        logger.info(event + ".started", extra={"stage": event, "status": "started"})
        try:
            yield outcome
        except BaseException as error:
            cancelled = isinstance(error, asyncio.CancelledError)
            logger.log(
                logging.INFO if cancelled else logging.ERROR,
                event + (".cancelled" if cancelled else ".failed"),
                extra={
                    "stage": event,
                    "status": "cancelled" if cancelled else "failed",
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
                exc_info=not cancelled,
            )
            raise
        else:
            logger.log(
                logging.ERROR if outcome["status"] == "failed" else logging.INFO,
                event + (".failed" if outcome["status"] == "failed" else ".completed"),
                extra={"stage": event, **outcome, "duration_ms": round((time.perf_counter() - started) * 1000, 2)},
            )


class RequestLoggingMiddleware:
    """Observe HTTP results without buffering request/response bodies or WebSockets."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started, status, trace_id, error_type = time.perf_counter(), 500, None, None
        cancelled = False

        async def observed_send(message):
            nonlocal status, trace_id
            if message["type"] == "http.response.start":
                status = message["status"]
                trace_id = current_trace_id()
                if trace_id:
                    message = {
                        **message,
                        "headers": [(k, v) for k, v in message.get("headers", []) if k.lower() != b"x-trace-id"]
                        + [(b"x-trace-id", trace_id.encode())],
                    }
            await send(message)

        try:
            await self.app(scope, receive, observed_send)
        except BaseException as error:
            cancelled = isinstance(error, asyncio.CancelledError)
            error_type = type(error).__name__
            raise
        finally:
            if scope.get("path") != "/health":
                route = getattr(scope.get("route"), "path", "unmatched")
                level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
                if scope.get("method") == "GET" and status < 400:
                    level = logging.DEBUG
                if error_type:
                    level = logging.INFO if cancelled else logging.ERROR
                identifiers = scope.get("path_params", {})
                business = next(
                    (
                        {key: identifiers[key]}
                        for key in ("document_id", "message_id", "chat_id")
                        if identifiers.get(key)
                    ),
                    {},
                )
                logging.getLogger("aperag.http").log(
                    level,
                    "http.request.cancelled"
                    if cancelled
                    else "http.request.failed"
                    if status >= 400 or error_type
                    else "http.request.completed",
                    extra={
                        "path": route,
                        "method": scope.get("method"),
                        "status_code": status,
                        "status": "cancelled" if cancelled else "failed" if status >= 400 or error_type else "success",
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                        "trace_id": trace_id or current_trace_id(),
                        "error_type": error_type,
                        **business,
                    },
                )
