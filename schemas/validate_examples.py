#!/usr/bin/env python3
"""Validate every JSON Schema and example under schemas/v0.3.

Requires the `jsonschema` package:
    python -m pip install jsonschema
    python schemas/validate_examples.py

Exit code 0 means all schemas are valid Draft 2020-12 schemas and every
example validates against its schema.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

SCHEMA_DIR = Path(__file__).with_name("v0.3")
EXAMPLES = {
    "item-state.json": "item-state.schema.json",
    "study-event.json": "study-event.schema.json",
    "engine-config.json": "engine-config.schema.json",
    "daily-plan.json": "daily-plan.schema.json",
    "export.json": "export.schema.json",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    schemas = {}
    resources = []
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        schema = load(path)
        Draft202012Validator.check_schema(schema)
        schemas[path.name] = schema
        resources.append((schema["$id"], Resource.from_contents(schema)))
        print(f"SCHEMA OK {path.relative_to(SCHEMA_DIR.parent.parent)}")

    registry = Registry().with_resources(resources)
    failures = 0
    for example_name, schema_name in EXAMPLES.items():
        data = load(SCHEMA_DIR / "examples" / example_name)
        validator = Draft202012Validator(schemas[schema_name], registry=registry)
        errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
        if errors:
            failures += 1
            print(f"FAIL {example_name}")
            for error in errors:
                print(f"  {list(error.path)}: {error.message}")
        else:
            print(f"EXAMPLE OK {example_name}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
