"""Bot save contract tests with real TS callbacks and Pydantic, no live services.

Run after installing the project's frontend dependencies:
    python -m pytest tests/contract/test_bot_config_contract.py
The Node harness mocks React hooks, UI, and API transport; it does not run a browser.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import get_args

import pytest
import yaml
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from aperag.schema import view_models as models  # noqa: E402


def callbacks(tmp_path, bot=None):
    command = ["node", str(ROOT / "tests/contract/bot_config_callbacks.cjs")]
    if bot is not None:
        fixture = tmp_path / "read-back-bot.json"
        fixture.write_text(json.dumps({"bot": bot}), encoding="utf-8")
        command.append(str(fixture))
    result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def captured(tmp_path_factory):
    return callbacks(tmp_path_factory.mktemp("bot-callbacks"))


@pytest.mark.parametrize("kind", ["bot", "intent", "normal", "quick"])
def test_actual_save_callbacks_serialize_read_back_and_edit(captured, tmp_path, kind):
    capture = next(c for c in captured["captures"] if c["kind"] == kind)
    update = models.BotUpdate.model_validate(capture["request"]["botUpdate"])
    # Match BotService's config serialization and response model parsing. The DB
    # replacement itself is intentionally a local substitute, not a live DB claim.
    serialized = update.config.model_dump_json(exclude_none=True)
    read_back = models.BotConfig.model_validate_json(serialized)
    assert json.loads(read_back.model_dump_json(exclude_none=True)) == json.loads(serialized)
    previous = models.BotConfig.model_validate(captured["bot"]["config"])
    assert read_back.flow == previous.flow
    assert read_back.orchestration.skills[1] == previous.orchestration.skills[1]
    assert read_back.orchestration.intent_router.fallback_skill_id == "two"
    assert (
        read_back.orchestration.intent_router.candidate_skills == previous.orchestration.intent_router.candidate_skills
    )
    assert read_back.agent == previous.agent
    if kind in {"normal", "quick"}:
        assert read_back.orchestration.skills[0].runtime == previous.orchestration.skills[0].runtime
        assert read_back.orchestration.skills[0].tools == previous.orchestration.skills[0].tools
        assert read_back.orchestration.skills[0].category == "operations"
    bot = {**captured["bot"], "config": json.loads(serialized)}
    repeated = callbacks(tmp_path, bot)
    assert len(repeated["captures"]) == 6


@pytest.mark.parametrize("kind", ["normal-clear", "quick-clear"])
def test_explicit_array_and_text_clears_survive_backend_serialization(captured, kind):
    capture = next(c for c in captured["captures"] if c["kind"] == kind)
    update = models.BotUpdate.model_validate(capture["request"]["botUpdate"])
    read_back = models.BotConfig.model_validate_json(update.config.model_dump_json(exclude_none=True))
    saved = read_back.orchestration.skills[0]
    assert saved.tools == []
    assert saved.collections == []
    assert saved.prompts.skill_prompt == ""
    assert saved.description == ""
    assert saved.runtime.top_p == 0.63
    assert saved.runtime.timeout_ms == 1717


def test_omitted_null_and_explicit_empty_values_remain_distinct():
    omitted = models.SkillRuntimeConfig()
    assert models.CandidateSkill(skill_id="one", label="one", examples=None).examples is None
    assert omitted.temperature == 0.7
    assert omitted.max_tokens == 2048
    assert omitted.top_p == 1
    assert omitted.timeout_ms == 30000
    explicit_null = models.SkillRuntimeConfig(temperature=None, max_tokens=None, top_p=None, timeout_ms=None)
    assert explicit_null.temperature is None and explicit_null.max_tokens is None
    assert explicit_null.model_dump(exclude_none=True) == {}
    assert "top_p" not in explicit_null.model_dump(exclude_none=True)
    assert models.SkillRuntimeConfig.model_validate_json(explicit_null.model_dump_json(exclude_none=True)).top_p == 1
    empty = models.SkillConfig(id="empty", name="", tools=[], collections=[])
    assert empty.tools == [] and empty.name == ""
    assert models.SkillConfig(id="default", name="default").tools == []
    empty.tools.append(models.SkillToolBinding(tool_id="isolated"))
    assert models.SkillConfig(id="other", name="other").tools == []


@pytest.mark.parametrize(
    "class_name,field,value",
    [
        ("CandidateSkill", "enabled", None),
        ("SkillConfig", "tools", None),
        ("OrchestrationConfig", "skills", None),
        ("ReactFlowSchema", "nodes", None),
        ("IntentRouterLLMConfig", "temperature", None),
        ("IntentRouterLLMConfig", "max_tokens", None),
    ],
)
def test_existing_nonnullable_fields_stay_nonnullable(class_name, field, value):
    cls = getattr(models, class_name)
    fixtures = {
        "CandidateSkill": {"skill_id": "one", "label": "one"},
        "SkillConfig": {"id": "one", "name": "one"},
        "OrchestrationConfig": {},
        "ReactFlowSchema": {"version": "1"},
        "IntentRouterLLMConfig": {"provider": "test", "model": "test"},
    }
    with pytest.raises(ValidationError):
        cls.model_validate({**fixtures[class_name], field: value})


def test_orchestration_source_schema_matches_backend_fields_defaults_and_requiredness():
    source = yaml.safe_load((ROOT / "aperag/api/components/schemas/orchestration.yaml").read_text(encoding="utf-8"))
    for class_name, schema in source.items():
        cls = getattr(models, class_name)
        assert set(schema["properties"]) == set(cls.model_fields), class_name
        assert set(schema.get("required", [])) == {
            name for name, field in cls.model_fields.items() if field.is_required()
        }, class_name
        for name, prop in schema["properties"].items():
            field = cls.model_fields[name]
            nullable = type(None) in get_args(field.annotation)
            schema_nullable = "null" in prop.get("type", []) or any(
                branch.get("type") == "null" for branch in prop.get("anyOf", [])
            )
            assert schema_nullable == nullable, (class_name, name)
            if "default" in prop:
                actual_default = field.default_factory() if field.default_factory else field.default
                assert actual_default == prop["default"], (class_name, name)


def test_bot_source_includes_existing_flags_welcome_and_orchestration():
    source = yaml.safe_load((ROOT / "aperag/api/components/schemas/bot.yaml").read_text(encoding="utf-8"))
    for name, cls in [("bot", models.Bot), ("botCreate", models.BotCreate), ("botUpdate", models.BotUpdate)]:
        assert set(source[name]["properties"]) == set(cls.model_fields)
        assert "is_default" in source[name]["properties"] and "is_protected" in source[name]["properties"]
    assert set(source["botConfig"]["properties"]) == set(models.BotConfig.model_fields)
    assert set(source["botConfig"]["properties"]["agent"]["properties"]) == set(models.Agent.model_fields)


def test_bot_update_flags_distinguish_false_from_omission():
    assert models.BotCreate().is_default is False
    assert models.BotCreate().is_protected is False
    omitted = models.BotUpdate()
    explicit_null = models.BotUpdate(is_default=None)
    disabled = models.BotUpdate(is_default=False)
    assert omitted.is_default is None and "is_default" not in omitted.model_fields_set
    assert "is_default" in explicit_null.model_fields_set
    assert disabled.model_dump(exclude_none=True)["is_default"] is False
