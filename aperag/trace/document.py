"""Spans for document work executed outside the API process.

Spans contain identifiers and operation outcomes, without exception text.
Application logs separately retain safe code locations and exception types.
"""

from functools import wraps
from inspect import signature

from opentelemetry.trace import StatusCode

from aperag.logging import log_stage

from .telemetry import init_telemetry, is_initialized
from .utils import get_tracer


def trace_document_operation(operation: str):
    """Trace parsing/index work, including failures returned as task results."""

    def decorate(func):
        parameters = signature(func)

        @wraps(func)
        def wrapped(*args, **kwargs):
            from aperag.config import settings

            arguments = parameters.bind(*args, **kwargs).arguments

            def invoke():
                fields = {key: arguments[key] for key in ("document_id", "index_type") if key in arguments}
                with log_stage(f"document.{operation}", **fields) as outcome:
                    result = func(*args, **kwargs)
                    if getattr(result, "success", True) is False:
                        outcome.update(status="failed", error_type="IndexTaskError")
                    return result

            if not settings.otel_enabled:
                return invoke()

            # Celery does not import aperag.app. Initialize in the executing
            # worker process, rather than starting exporter threads before fork.
            if not is_initialized():
                init_telemetry(
                    service_name=settings.otel_service_name,
                    service_version=settings.otel_service_version,
                    langfuse_enabled=settings.langfuse_enabled,
                    langfuse_base_url=settings.langfuse_base_url,
                    langfuse_public_key=settings.langfuse_public_key,
                    langfuse_secret_key=settings.langfuse_secret_key,
                    enable_console=settings.otel_console_enabled,
                )

            tracer = get_tracer(__name__)
            if tracer is None:
                return invoke()

            attributes = {"document_id": arguments["document_id"], "operation": operation}
            if "index_type" in arguments:
                attributes["index_type"] = arguments["index_type"]
            parsed_data = arguments.get("parsed_data")
            if parsed_data is not None:
                attributes["collection_id"] = parsed_data.collection_id

            with tracer.start_as_current_span(
                f"document.{operation}",
                attributes=attributes,
                record_exception=False,
                set_status_on_exception=False,
            ) as span:
                try:
                    result = invoke()
                except BaseException as error:
                    span.set_attribute("success", False)
                    span.set_attribute("task.status", "failed")
                    span.set_attribute("error.type", type(error).__name__)
                    span.set_status(StatusCode.ERROR)
                    raise

                success = getattr(result, "success", True)
                span.set_attribute("success", success)
                span.set_attribute("task.status", "success" if success else "failed")
                span.set_status(StatusCode.OK if success else StatusCode.ERROR)
                return result

        return wrapped

    return decorate
