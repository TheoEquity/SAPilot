"""Exercise Python-owned contracts, documentation and export without live services."""

import importlib.util
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def exporter():
    spec = importlib.util.spec_from_file_location("export_openapi", ROOT / "scripts/export_openapi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_app():
    from aperag.schema.view_models import Bot, BotUpdate

    app = FastAPI(title="Contract test")

    @app.put("/api/v1/bots/{bot_id}", tags=["bots"], operation_id="updateBot")
    def update_bot(bot_id: str, body: BotUpdate) -> Bot:
        return Bot(id=bot_id, **body.model_dump(exclude={"id"}))

    @app.get("/api/v1/documents", tags=["documents"], operation_id="listDocuments")
    def documents() -> list[str]:
        return []

    return app


def test_export_uses_real_python_models_and_serves_the_same_docs(tmp_path):
    app = sample_app()
    with TestClient(app) as client:
        document = client.get("/openapi.json").json()
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200
        response = client.put("/api/v1/bots/one", json={"is_default": False})
        assert response.status_code == 200
        assert response.json()["is_default"] is False
    exporter().export_document(document, tmp_path)
    assert json.loads((tmp_path / "openapi.json").read_text()) == document
    bots = json.loads((tmp_path / "modules/bots.json").read_text())
    assert set(bots["paths"]) == {"/api/v1/bots/{bot_id}"}
    schema = bots["components"]["schemas"]["BotUpdate"]
    assert {"config", "is_default", "is_protected"} <= schema["properties"].keys()
    assert "../openapi.json" in (tmp_path / "docs/index.html").read_text()
    assert "../openapi.json" in (tmp_path / "docs/redoc.html").read_text()
    before = (tmp_path / "openapi.json").read_bytes()
    exporter().export_document(document, tmp_path)
    assert (tmp_path / "openapi.json").read_bytes() == before


def test_new_python_route_and_field_are_discovered_without_yaml(tmp_path):
    app = sample_app()

    class CreateInput(BaseModel):
        title: str
        optional_note: str | None = None

    @app.post("/api/v1/new", tags=["new"], operation_id="createNew")
    def create_new(body: CreateInput) -> CreateInput:
        return body

    summary = exporter().export_document(app.openapi(), tmp_path, ["new"])
    assert summary["operations"] == 1
    assert not (tmp_path / "openapi.json").exists()
    document = json.loads((tmp_path / "modules/new.json").read_text())
    assert set(document["paths"]) == {"/api/v1/new"}
    schema = document["components"]["schemas"]["CreateInput"]
    assert set(schema["properties"]) == {"title", "optional_note"}
    assert schema["required"] == ["title"]


@pytest.mark.parametrize("problem", ["duplicate_id", "missing_ref", "unknown_module"])
def test_invalid_export_leaves_published_documents_unchanged(tmp_path, problem):
    module = exporter()
    document = sample_app().openapi()
    module.export_document(document, tmp_path)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    modules = []
    if problem == "duplicate_id":
        document["paths"]["/api/v1/documents"]["get"]["operationId"] = "updateBot"
    elif problem == "missing_ref":
        document["components"]["schemas"]["Broken"] = {"$ref": "#/components/schemas/Missing"}
    else:
        modules = ["missing"]
    with pytest.raises(ValueError):
        module.export_document(document, tmp_path, modules)
    assert before == {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


def test_generated_client_preserves_browser_and_server_transport_contracts():
    result = subprocess.run(
        ["node", str(ROOT / "tests/contract/code_first_client.cjs")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {"requests": 5, "browserAndServer": True, "preservedPayloadAndErrors": True}


def test_cli_exports_from_an_http_schema_endpoint(tmp_path):
    document = sample_app().openapi()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(document).encode())

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/export_openapi.py"),
                    "--url",
                    f"http://127.0.0.1:{server.server_port}/openapi.json",
                    "--output",
                    str(tmp_path),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        finally:
            server.shutdown()
            thread.join()
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "openapi.json").read_text()) == document


def test_output_alias_cannot_redirect_published_contracts(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    alias = tmp_path / "output"
    subprocess.run(
        [
            "node",
            "-e",
            "require('node:fs').symlinkSync(process.argv[1], process.argv[2], 'junction')",
            str(source),
            str(alias),
        ],
        check=True,
    )
    with pytest.raises(ValueError):
        exporter().export_document(sample_app().openapi(), alias)
    assert not list(source.iterdir())
