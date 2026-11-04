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
Core OpenTelemetry initialization - simplified version.
"""

import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# OpenTelemetry imports with graceful fallback
try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning("OpenTelemetry not available - tracing disabled")


class NoOpSpanExporter(SpanExporter):
    """A no-op span exporter that discards all spans silently."""

    def export(self, spans):
        """Export spans by discarding them."""
        return trace.StatusCode.OK

    def shutdown(self):
        """Shutdown the exporter."""
        pass


try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    OTLP_AVAILABLE = True
except ImportError:
    OTLP_AVAILABLE = False

# Global initialization flag
_telemetry_initialized = False


def is_telemetry_available() -> bool:
    """Check if OpenTelemetry is available."""
    return OTEL_AVAILABLE


def init_telemetry(
    service_name: str = "aperag",
    service_version: str = "1.0.0",
    enable_console: bool = True,
    langfuse_enabled: bool = False,
    langfuse_base_url: Optional[str] = None,
    langfuse_public_key: Optional[str] = None,
    langfuse_secret_key: Optional[str] = None,
) -> bool:
    """
    Initialize OpenTelemetry tracing.

    Args:
        service_name: Name of the service
        service_version: Version of the service
        enable_console: Whether to enable console output
        langfuse_enabled: Export traces to the configured Langfuse project.
        langfuse_base_url: Langfuse instance base URL.
        langfuse_public_key: Project public API key.
        langfuse_secret_key: Project secret API key; never logged.

    Returns:
        True if initialization succeeded, False otherwise
    """
    global _telemetry_initialized

    if _telemetry_initialized:
        logger.debug("OpenTelemetry already initialized")
        return True

    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available - tracing disabled")
        return False

    if langfuse_enabled and not (OTLP_AVAILABLE and langfuse_base_url and langfuse_public_key and langfuse_secret_key):
        logger.error("Langfuse tracing requires the OTLP/HTTP exporter, base URL and both project API keys")
        return False

    try:
        # Create resource with service information
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": service_version,
                "service.environment": os.getenv("ENVIRONMENT", "development"),
            }
        )

        # Create TracerProvider
        tracer_provider = TracerProvider(resource=resource)

        # Configure exporters
        exporters_added = 0

        if langfuse_enabled:
            from .langfuse import LangfuseSpanProcessor

            tracer_provider.add_span_processor(LangfuseSpanProcessor())
            authentication = base64.b64encode(f"{langfuse_public_key}:{langfuse_secret_key}".encode()).decode()
            exporter = OTLPSpanExporter(
                endpoint=langfuse_base_url.rstrip("/") + "/api/public/otel/v1/traces",
                headers={"Authorization": "Basic " + authentication, "x-langfuse-ingestion-version": "4"},
            )
            tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
            exporters_added += 1
            logger.info("Langfuse OTLP/HTTP exporter configured")

        # Add console exporter if explicitly enabled
        if enable_console:
            try:
                console_exporter = ConsoleSpanExporter()
                console_processor = BatchSpanProcessor(console_exporter)
                tracer_provider.add_span_processor(console_processor)
                exporters_added += 1
                logger.info("✅ Console exporter configured")
            except Exception as e:
                logger.warning(f"Failed to configure console exporter: {e}")

        # If no exporters were configured, use a no-op exporter to keep tracing functional
        if exporters_added == 0:
            try:
                noop_exporter = NoOpSpanExporter()
                noop_processor = BatchSpanProcessor(noop_exporter)
                tracer_provider.add_span_processor(noop_processor)
                exporters_added += 1
                logger.info("✅ No-op exporter configured (tracing enabled, no output)")
            except Exception as e:
                logger.warning(f"Failed to configure no-op exporter: {e}")
                return False

        # Set the global tracer provider
        trace.set_tracer_provider(tracer_provider)

        _telemetry_initialized = True
        logger.info("OpenTelemetry initialized successfully")

        return True

    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")
        return False


def is_initialized() -> bool:
    """Check if telemetry has been initialized."""
    return _telemetry_initialized
