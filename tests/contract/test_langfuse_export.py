"""Real OTLP/HTTP transport against a local collector double, in fresh SDK processes."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_isolated(code):
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stdout + result.stderr


def test_langfuse_export_uses_authenticated_otlp_http_and_preserves_spans():
    run_isolated("""
import base64
import importlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from opentelemetry import trace
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

requests = []
class Collector(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = ExportTraceServiceRequest()
        payload.ParseFromString(self.rfile.read(int(self.headers['Content-Length'])))
        requests.append((self.path, dict(self.headers), payload))
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-protobuf')
        self.end_headers()
    def log_message(self, *args):
        pass

server = HTTPServer(('127.0.0.1', 0), Collector)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
module = vars(importlib.import_module('aperag.trace.telemetry'))
initialize = module['init_telemetry']
kwargs = dict(service_name='sapilot-test', enable_console=False, langfuse_enabled=True,
              langfuse_base_url=f'http://127.0.0.1:{server.server_port}/',
              langfuse_public_key='test-public', langfuse_secret_key='test-secret')
assert initialize(**kwargs)
assert initialize(**kwargs)
with trace.get_tracer('test').start_as_current_span('document.parse') as span:
    span.set_attribute('document_id', 'test-document')
assert trace.get_tracer_provider().force_flush()
trace.get_tracer_provider().shutdown()
server.shutdown()
server.server_close()
assert len(requests) == 1, 'Initialization must not register duplicate exporters'
path, headers, request = requests[0]
headers = {k.lower(): v for k, v in headers.items()}
assert path == '/api/public/otel/v1/traces'
expected = base64.b64encode(b'test-public:test-secret').decode()
assert headers['authorization'] == 'Basic ' + expected
assert headers['x-langfuse-ingestion-version'] == '4'
assert headers['content-type'] == 'application/x-protobuf'
spans = [s for r in request.resource_spans for scope in r.scope_spans for s in scope.spans]
assert [s.name for s in spans] == ['document.parse']
assert any(a.key == 'document_id' and a.value.string_value == 'test-document' for a in spans[0].attributes)
""")


def test_enabled_langfuse_without_credentials_does_not_report_success():
    run_isolated("""
import importlib
module = vars(importlib.import_module('aperag.trace.telemetry'))
assert module['init_telemetry'](langfuse_enabled=True, langfuse_base_url='http://localhost:3300',
                                langfuse_public_key='', langfuse_secret_key='', enable_console=False) is False
assert not module['is_initialized']()
""")


def test_mcp_observations_preserve_sessions_and_do_not_count_model_selection_as_generation():
    run_isolated("""
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from aperag.trace.langfuse import LangfuseSpanProcessor

provider = TracerProvider()
provider.add_span_processor(LangfuseSpanProcessor())
exported = InMemorySpanExporter()
provider.add_span_processor(SimpleSpanProcessor(exported))
tracer = provider.get_tracer('test')
with tracer.start_as_current_span('chat.message') as root:
    root.set_attribute('langfuse.session.id', 'chat-test')
    root.set_attribute('langfuse.user.id', 'user-test')
    root.set_attribute('langfuse.trace.name', 'chat.message')
    root.set_attribute('private.input', 'do-not-propagate')
    with tracer.start_as_current_span('OpenAIAugmentedLLM.test.select_model') as model:
        model.set_attribute('model', 'test-model')
    with tracer.start_as_current_span('OpenAIAugmentedLLM.test.generate_str'):
        pass
    with tracer.start_as_current_span('MCPAggregator.call_tool'):
        with tracer.start_as_current_span('retrieval'):
            pass
spans = {x.name: x for x in exported.get_finished_spans()}
assert spans['OpenAIAugmentedLLM.test.select_model'].attributes['langfuse.observation.type'] == 'span'
assert spans['OpenAIAugmentedLLM.test.generate_str'].attributes['langfuse.observation.type'] == 'span'
assert spans['MCPAggregator.call_tool'].attributes['langfuse.observation.type'] == 'tool'
for name in ['OpenAIAugmentedLLM.test.select_model', 'MCPAggregator.call_tool', 'retrieval']:
    assert spans[name].attributes['langfuse.session.id'] == 'chat-test'
    assert spans[name].attributes['langfuse.user.id'] == 'user-test'
    assert spans[name].attributes['langfuse.trace.name'] == 'chat.message'
    assert 'private.input' not in spans[name].attributes
provider.shutdown()
""")
