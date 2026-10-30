"""Exercise discovery and bundling through the real OpenAPI build command."""

import json
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMMAND = ROOT / "scripts" / "build-openapi.cjs"


def write_yaml(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def api(tmp_path):
    source = tmp_path / "api"
    write_yaml(
        source / "openapi.yaml",
        {"openapi": "3.1.0", "info": {"title": "Test", "version": "1"}},
    )
    return source


def operation(api, module, name, path, method="get", **fields):
    write_yaml(
        api / "paths" / module / f"{name}.yaml",
        {path: {method: {"responses": {"200": {"description": "OK"}}, **fields}}},
    )


def build(api, output, *args):
    return subprocess.run(
        ["node", str(COMMAND), "--source", str(api), "--output", str(output), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def read_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_new_file_is_discovered_without_root_registration(api, tmp_path):
    operation(api, "bots", "list", "/bots")
    output = tmp_path / "output"
    result = build(api, output)
    assert result.returncode == 0, result.stderr
    metadata = (api / "openapi.yaml").read_bytes()

    operation(api, "bots", "create", "/bots", "post")
    operation(api, "documents", "list", "/documents")
    result = build(api, output)
    assert result.returncode == 0, result.stderr
    combined = read_yaml(output / "openapi.yaml")
    assert set(combined["paths"]) == {"/bots", "/documents"}
    assert set(combined["paths"]["/bots"]) == {"get", "post"}
    assert set(read_yaml(output / "modules" / "bots.yaml")["paths"]) == {"/bots"}
    assert set(read_yaml(output / "modules" / "documents.yaml")["paths"]) == {"/documents"}
    assert (api / "openapi.yaml").read_bytes() == metadata
    first = {p.relative_to(output): p.read_bytes() for p in output.rglob("*.yaml")}
    assert build(api, output).returncode == 0
    assert first == {p.relative_to(output): p.read_bytes() for p in output.rglob("*.yaml")}


def test_module_only_output_does_not_require_one_combined_file(api, tmp_path):
    operation(api, "bots", "list", "/bots")
    operation(api, "documents", "list", "/documents")
    result = build(api, tmp_path / "output", "--module", "bots")
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "output" / "openapi.yaml").exists()
    assert set((tmp_path / "output" / "modules").glob("*.yaml")) == {tmp_path / "output" / "modules" / "bots.yaml"}


def test_agent_chat_controls_remain_in_the_bundled_contract(tmp_path):
    import sys

    sys.path.insert(0, str(ROOT))
    from aperag.schema.view_models import AgentMessage

    result = build(ROOT / "aperag/api", tmp_path / "output", "--module", "agent")
    assert result.returncode == 0, result.stderr
    contract = read_yaml(tmp_path / "output/modules/agent.yaml")["components"]["schemas"]["AgentMessage"]
    runtime = AgentMessage.model_json_schema()
    for name in ("force_skill_id", "action"):
        assert name in contract["properties"]
        assert set(contract["properties"][name]["type"]) == {
            item["type"] for item in runtime["properties"][name]["anyOf"]
        }
        assert name not in contract["required"]


def test_shared_schema_is_resolved_in_each_standalone_module(api, tmp_path):
    write_yaml(
        api / "components" / "schemas" / "shared.yaml",
        {"Item": {"type": "object", "properties": {"id": {"type": "string"}}}},
    )
    for module in ("bots", "documents"):
        operation(
            api,
            module,
            "list",
            f"/{module}",
            responses={
                "200": {
                    "description": "OK",
                    "content": {"application/json": {"schema": {"$ref": "../../components/schemas/shared.yaml#/Item"}}},
                }
            },
        )
    result = build(api, tmp_path / "output")
    assert result.returncode == 0, result.stderr
    for module in ("bots", "documents"):
        document = read_yaml(tmp_path / "output" / "modules" / f"{module}.yaml")
        ref = document["paths"][f"/{module}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        assert ref.startswith("#/components/schemas/")
        schema = document
        for token in ref[2:].split("/"):
            schema = schema[token]
        assert schema["properties"]["id"] == {"type": "string"}


def test_marketplace_errors_use_response_objects_with_a_json_body(tmp_path):
    output = tmp_path / "output"
    result = build(ROOT / "aperag/api", output, "--module", "marketplace")
    assert result.returncode == 0, result.stderr
    document = read_yaml(output / "modules/marketplace.yaml")
    for item in document["paths"].values():
        for operation in item.values():
            for status in ("401", "500"):
                response = operation["responses"][status]
                assert response.get("description")
                ref = response["content"]["application/json"]["schema"]["$ref"]
                schema = document
                for token in ref[2:].split("/"):
                    schema = schema[token]
                assert schema["type"] == "object"
                assert set(schema["properties"]) == {"code", "message"}


def test_generated_output_cannot_overwrite_source_metadata(api):
    operation(api, "bots", "list", "/bots")
    before = (api / "openapi.yaml").read_bytes()
    result = build(api, api)
    assert result.returncode != 0
    assert (api / "openapi.yaml").read_bytes() == before


@pytest.mark.parametrize("link_at", ["output", "modules"])
def test_output_directory_alias_cannot_redirect_writes_into_sources(api, tmp_path, link_at):
    operation(api, "bots", "list", "/bots")
    output = tmp_path / "output"
    alias = output if link_at == "output" else output / "modules"
    alias.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "node",
            "-e",
            "require('node:fs').symlinkSync(process.argv[1], process.argv[2], 'junction')",
            str(api),
            str(alias),
        ],
        check=True,
    )
    before = {p.relative_to(api): p.read_bytes() for p in api.rglob("*.yaml")}
    result = build(api, output)
    assert result.returncode != 0
    assert before == {p.relative_to(api): p.read_bytes() for p in api.rglob("*.yaml")}
    if link_at == "modules":
        assert not (output / "openapi.yaml").exists()


def test_equivalent_path_parameters_merge_across_independent_methods(api, tmp_path):
    parameter = {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
    write_yaml(
        api / "paths/bots/get.yaml",
        {
            "/bots/{id}": {
                "parameters": [parameter],
                "get": {"responses": {"200": {"description": "OK"}}},
            }
        },
    )
    write_yaml(
        api / "paths/bots/delete.yaml",
        {
            "/bots/{id}": {
                "parameters": [dict(reversed(list(parameter.items())))],
                "delete": {"responses": {"204": {"description": "Deleted"}}},
            }
        },
    )
    result = build(api, tmp_path / "output")
    assert result.returncode == 0, result.stderr
    item = read_yaml(tmp_path / "output/openapi.yaml")["paths"]["/bots/{id}"]
    assert set(item) == {"parameters", "get", "delete"}
    assert item["parameters"] == [parameter]


def test_same_templated_route_cannot_be_registered_with_different_parameter_names(api, tmp_path):
    operation(api, "bots", "one", "/bots/{id}")
    operation(api, "bots", "two", "/bots/{bot_id}")
    result = build(api, tmp_path / "output")
    assert result.returncode != 0
    assert not (tmp_path / "output/openapi.yaml").exists()


@pytest.mark.parametrize(
    "problem", ["duplicate_route", "duplicate_id", "missing_ref", "multiple_operations", "duplicate_yaml_key"]
)
def test_invalid_sources_fail_without_overwriting_outputs(api, tmp_path, problem):
    operation(api, "bots", "list", "/bots", operationId="listBots")
    output = tmp_path / "output"
    assert build(api, output).returncode == 0
    before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*.yaml")}
    if problem == "duplicate_route":
        operation(api, "bots", "another", "/bots")
    elif problem == "duplicate_id":
        operation(api, "bots", "another", "/other", operationId="listBots")
    elif problem == "missing_ref":
        operation(api, "bots", "another", "/other", responses={"200": {"$ref": "missing.yaml#/response"}})
    elif problem == "multiple_operations":
        write_yaml(api / "paths" / "bots" / "another.yaml", {"/other": {"get": {}, "post": {}}})
    else:
        (api / "paths" / "bots" / "another.yaml").write_text("/other:\n  get: {}\n  get: {}\n", encoding="utf-8")
    result = build(api, output)
    assert result.returncode != 0
    assert result.stderr.strip()
    assert before == {p.relative_to(output): p.read_bytes() for p in output.rglob("*.yaml")}
