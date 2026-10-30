"""Export Python-owned FastAPI contracts and their browsable documentation."""

import argparse
import importlib
import json
import re
import stat
import sys
from copy import deepcopy
from pathlib import Path
from urllib.request import urlopen

from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html

ROOT = Path(__file__).resolve().parents[1]
METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


def validate_document(document):
    if not isinstance(document, dict) or not document.get("openapi") or not document.get("paths"):
        raise ValueError("Expected an OpenAPI document with HTTP paths")
    identities = set()
    for item in document["paths"].values():
        for method, operation in item.items():
            if method not in METHODS:
                continue
            identity = operation.get("operationId")
            if not identity or identity in identities:
                raise ValueError(f"Missing or duplicate operationId: {identity}")
            identities.add(identity)

    def check(value):
        if isinstance(value, dict):
            if "$ref" in value:
                ref = value["$ref"]
                if not isinstance(ref, str) or not ref.startswith("#/"):
                    raise ValueError(f"Expected an internal reference: {ref}")
                target = document
                for token in ref[2:].split("/"):
                    key = token.replace("~1", "/").replace("~0", "~")
                    if not isinstance(target, dict) or key not in target:
                        raise ValueError(f"Unresolved reference: {ref}")
                    target = target[key]
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)

    check(document)


def export_document(document, output, modules=()):
    validate_document(document)
    grouped = {}
    for route, item in document["paths"].items():
        fields = {key: value for key, value in item.items() if key not in METHODS}
        for method, operation in item.items():
            if method not in METHODS:
                continue
            for tag in operation.get("tags") or ["default"]:
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", tag):
                    raise ValueError(f"Use a filesystem-safe API tag: {tag}")
                grouped.setdefault(tag, {}).setdefault(route, {**fields})[method] = operation
    selected = sorted(set(modules)) or sorted(grouped)
    if set(selected) - grouped.keys():
        raise ValueError(f"Unknown modules: {sorted(set(selected) - grouped.keys())}")

    def encode(value):
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")

    artifacts = {}
    if not modules:
        artifacts["openapi.json"] = encode(document)
        artifacts["docs/index.html"] = get_swagger_ui_html(
            openapi_url="../openapi.json", title=f"{document['info']['title']} - Swagger UI"
        ).body
        artifacts["docs/redoc.html"] = get_redoc_html(
            openapi_url="../openapi.json", title=f"{document['info']['title']} - ReDoc"
        ).body
    for name in selected:
        module = deepcopy(document)
        module["paths"] = grouped[name]
        artifacts[f"modules/{name}.json"] = encode(module)

    output = Path(output).absolute()
    # Check every destination before publishing any file, including directory aliases.
    for name in artifacts:
        target = output / name
        if target.resolve().is_relative_to(ROOT / "aperag"):
            raise ValueError("Generated contracts must stay outside backend source code")
        for parent in [target, *target.parents]:
            try:
                attributes = getattr(parent.lstat(), "st_file_attributes", 0)
            except FileNotFoundError:
                attributes = 0
            if parent.is_symlink() or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
                raise ValueError(f"Output contains a symbolic link or junction: {parent}")
            if parent == output:
                break
    for name, content in artifacts.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    covered = {
        (route, method)
        for name in selected
        for route, item in grouped[name].items()
        for method in item
        if method in METHODS
    }
    return {
        "operations": len(covered),
        "modules": selected,
        "output": str(output),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--url", help="Running backend's OpenAPI URL (default: http://localhost:8000/openapi.json)")
    source.add_argument(
        "--app", help="Import an installed backend app without running its lifespan, e.g. aperag.app:app"
    )
    parser.add_argument("--output", type=Path, default=ROOT / ".run/openapi")
    parser.add_argument("--module", action="append", default=[])
    args = parser.parse_args()
    if args.app:
        sys.path.insert(0, str(ROOT))
        module, name = args.app.split(":", 1)
        document = getattr(importlib.import_module(module), name).openapi()
    else:
        with urlopen(args.url or "http://localhost:8000/openapi.json", timeout=15) as response:
            document = json.load(response)
    print(json.dumps(export_document(document, args.output, args.module), ensure_ascii=False))


if __name__ == "__main__":
    main()
