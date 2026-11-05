#!/usr/bin/env python3
"""Run the RPE v0.3 business conformance scenarios.

Usage:
    python conformance/business/run_business_scenarios.py

Exit code 0 means every scenario passed. Exit code 1 means at least one failed.
No third-party dependencies are required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from reference_engine import Engine, Item, queue_after_reinsert

SCENARIO_PATH = Path(__file__).with_name("scenarios.json")


def make_item(spec: dict[str, Any], prefix: str, index: int) -> Item:
    item_id = spec.get("itemId") or f"{prefix}{index}"
    return Item(
        item_id=item_id,
        lifecycle=spec.get("lifecycle", "queued"),
        stability=spec.get("stabilityDays"),
        difficulty=spec.get("difficulty"),
        due_day=spec.get("dueDay"),
        last_review_day=spec.get("lastReviewDay"),
        last_interval_days=spec.get("lastIntervalDays"),
        reps=spec.get("reps", 0),
        lapses=spec.get("lapses", 0),
        first_learned_day=spec.get("firstLearnedDay"),
        epoch=spec.get("epoch", 1),
    )


def build_engine(case: dict[str, Any], defaults: dict[str, Any]) -> Engine:
    config = dict(defaults)
    config.update(case.get("config", {}))
    engine = Engine(config)

    for spec in case.get("items", []):
        engine.add_item(make_item(spec, spec.get("itemId", "item"), 1))

    for group in case.get("generate", []):
        prefix = group["prefix"]
        start = group.get("start", 1)
        for index in range(start, start + int(group["count"])):
            engine.add_item(make_item(group, prefix, index))

    return engine


def execute(
    case: dict[str, Any], defaults: dict[str, Any]
) -> tuple[Engine, dict[str, Any]]:
    engine = build_engine(case, defaults)
    context: dict[str, Any] = {}

    for step in case.get("steps", []):
        op = step["op"]
        if op == "rate":
            engine.rate(
                item_id=step["itemId"],
                rating=step["rating"],
                day_key=step["dayKey"],
                context=step.get("context", "scheduled"),
                command_id=step.get("commandId"),
                was_new=step.get("wasNew"),
            )
        elif op == "rate_many":
            prefix = step["prefix"]
            start = step.get("start", 1)
            command_prefix = step.get("commandPrefix", "c")
            for index in range(start, start + int(step["count"])):
                engine.rate(
                    item_id=f"{prefix}{index}",
                    rating=step["rating"],
                    day_key=step["dayKey"],
                    context=step.get("context", "scheduled"),
                    command_id=f"{command_prefix}{index}",
                    was_new=step.get("wasNew"),
                )
        elif op == "plan":
            context["plan"] = engine.plan(int(step["today"]))
        elif op == "queue":
            context["queue"] = queue_after_reinsert(
                list(step["queue"]), step["currentId"], step.get("gap")
            )
        else:
            raise ValueError(f"unknown step op: {op}")

    return engine, context


def compare(
    actual: Any, expected: Any, path: str, failures: list[str]
) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            failures.append(f"{path}: expected object, got {type(actual).__name__}")
            return
        for key, expected_value in expected.items():
            if key not in actual:
                failures.append(f"{path}.{key}: missing")
                continue
            compare(actual[key], expected_value, f"{path}.{key}", failures)
        return

    if isinstance(expected, list):
        if not isinstance(actual, list):
            failures.append(f"{path}: expected array, got {type(actual).__name__}")
            return
        if len(actual) != len(expected):
            failures.append(
                f"{path}: expected {len(expected)} entries, got {len(actual)}"
            )
            return
        for index, expected_value in enumerate(expected):
            compare(actual[index], expected_value, f"{path}[{index}]", failures)
        return

    if isinstance(expected, float):
        if not isinstance(actual, (int, float)) or abs(actual - expected) > 1e-6:
            failures.append(f"{path}: expected {expected}, got {actual!r}")
        return

    if actual != expected:
        failures.append(f"{path}: expected {expected!r}, got {actual!r}")


def check_case(
    case: dict[str, Any], defaults: dict[str, Any]
) -> list[str]:
    engine, context = execute(case, defaults)
    expected = case.get("expect", {})
    failures: list[str] = []

    if "items" in expected:
        for item_id, item_expected in expected["items"].items():
            if item_id not in engine.items:
                failures.append(f"items.{item_id}: missing")
                continue
            compare(
                engine.item_view(item_id),
                item_expected,
                f"items.{item_id}",
                failures,
            )

    if "events" in expected:
        compare(len(engine.events), expected["events"], "events", failures)

    if "plan" in expected:
        if "plan" not in context:
            failures.append("plan: missing (no plan step ran)")
        else:
            plan = dict(context["plan"])
            plan["reviewCount"] = len(plan["reviewIds"])
            plan["newCount"] = len(plan["newIds"])
            plan["advancedCount"] = len(plan["advancedIds"])
            compare(plan, expected["plan"], "plan", failures)

    if "queue" in expected:
        if "queue" not in context:
            failures.append("queue: missing (no queue step ran)")
        else:
            compare(context["queue"], expected["queue"], "queue", failures)

    return failures


def main() -> int:
    with SCENARIO_PATH.open(encoding="utf-8") as handle:
        document = json.load(handle)

    defaults = document["defaults"]
    cases = document["cases"]
    failures = 0

    print(f"RPE business conformance {document['specVersion']} ({document['strategy']})")
    for case in cases:
        case_failures = check_case(case, defaults)
        if case_failures:
            failures += 1
            print(f"FAIL {case['id']}: {case['description']}")
            for failure in case_failures:
                print(f"     {failure}")
        else:
            print(f"PASS {case['id']}: {case['description']}")

    print()
    print(f"{len(cases) - failures}/{len(cases)} scenarios passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
