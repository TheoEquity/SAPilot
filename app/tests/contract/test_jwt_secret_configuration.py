"""Validate the actual settings classes without loading local secrets or DB engines."""

import ast
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@pytest.fixture
def config_class(tmp_path):
    source = Path(__file__).resolve().parents[2] / "aperag/config.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    module = ast.Module(
        body=[node for node in tree.body if isinstance(node, ast.ClassDef)
              and node.name in {"S3Config", "LocalObjectStoreConfig", "Config"}],
        type_ignores=[],
    )
    scope = dict(
        Any=Any, Dict=Dict, Optional=Optional, Field=Field,
        BaseSettings=BaseSettings, SettingsConfigDict=SettingsConfigDict,
        field_validator=field_validator, BASE_DIR=tmp_path, json=json, os=os,
    )
    exec(compile(module, str(source), "exec"), scope)
    return scope["Config"]


@pytest.mark.parametrize("value", [None, "", "SECRET", "short-secret", " " * 64])
def test_missing_or_weak_secret_rejects_startup(config_class, monkeypatch, value):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    if value is not None:
        monkeypatch.setenv("JWT_SECRET", value)
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        config_class()


def test_existing_secret_is_preserved_across_instances(config_class, monkeypatch):
    secret = "test-only-" + "9b0f72d8" * 7
    monkeypatch.setenv("JWT_SECRET", secret)
    assert config_class().jwt_secret == secret
    assert config_class().jwt_secret == secret


def test_validation_error_does_not_print_secret(config_class, monkeypatch):
    secret = "private-short-secret"
    monkeypatch.setenv("JWT_SECRET", secret)
    with pytest.raises(ValidationError) as error:
        config_class()
    assert secret not in str(error.value)
