"""Map existing MCP spans and conversation identifiers to Langfuse observations."""

from opentelemetry import trace
from opentelemetry.sdk.trace import SpanProcessor


class LangfuseSpanProcessor(SpanProcessor):
    def on_start(self, span, parent_context=None):
        parent = trace.get_current_span(parent_context)
        attributes = getattr(parent, "attributes", None) or {}
        for key in ("langfuse.session.id", "langfuse.user.id", "langfuse.trace.name"):
            if key in attributes:
                span.set_attribute(key, attributes[key])

        # Model selection only reports configuration. Langfuse otherwise infers
        # a generation from its model attribute and counts it as an LLM call.
        if span.name.endswith((".select_model", ".generate_str")):
            span.set_attribute("langfuse.observation.type", "span")
        elif span.name.endswith(".call_tool") or span.name.endswith(".execute_tool_call"):
            span.set_attribute("langfuse.observation.type", "tool")

    def on_end(self, span):
        pass

    def force_flush(self, timeout_millis=30000):
        # This processor buffers nothing. Returning True lets the provider
        # continue flushing the OTLP batch processor registered after it.
        return True
