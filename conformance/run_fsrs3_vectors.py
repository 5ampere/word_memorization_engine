#!/usr/bin/env python3
"""Run the language-neutral FSRS-3 conformance vectors.

Usage:
    python conformance/run_fsrs3_vectors.py

Exit code 0 means every vector passed; 1 means at least one mismatch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

from fsrs3_reference import MemoryState, schedule


def _close(actual: Optional[float], expected: Optional[float], tolerance: float) -> bool:
    if expected is None:
        return actual is None
    if actual is None:
        return False
    return abs(actual - expected) <= tolerance


def _load_state(raw: Any) -> Optional[MemoryState]:
    if raw is None:
        return None
    return MemoryState(
        stability_days=float(raw["stabilityDays"]),
        difficulty=float(raw["difficulty"]),
    )


def main() -> int:
    root = Path(__file__).resolve().parent
    payload = json.loads((root / "fsrs3-vectors.json").read_text(encoding="utf-8"))

    weights = payload["weights"]
    tolerance = float(payload["tolerance"])
    target_retention = float(payload["targetRetention"])
    max_interval_days = int(payload["maxIntervalDays"])
    vague_max_interval_days = payload["vagueMaxIntervalDays"]
    if vague_max_interval_days is not None:
        vague_max_interval_days = int(vague_max_interval_days)

    failures = 0
    print(f"spec={payload['specVersion']} policy={payload['policyId']}@{payload['policyVersion']}")
    print(f"vectors={len(payload['vectors'])} tolerance={tolerance}")
    print()

    for vector in payload["vectors"]:
        vector_id = vector["id"]
        inputs = vector["input"]
        expected = vector["expect"]

        decision = schedule(
            _load_state(inputs["state"]),
            inputs["rating"],
            float(inputs["elapsedDays"]),
            target_retention=target_retention,
            max_interval_days=max_interval_days,
            vague_max_interval_days=vague_max_interval_days,
            weights=weights,
        )

        actual_state = decision.state
        checks = [
            (
                "stabilityDays",
                None if actual_state is None else actual_state.stability_days,
                expected["stabilityDays"],
                "close",
            ),
            (
                "difficulty",
                None if actual_state is None else actual_state.difficulty,
                expected["difficulty"],
                "close",
            ),
            (
                "retrievability",
                decision.retrievability,
                expected["retrievability"],
                "close",
            ),
            (
                "policyIntervalDays",
                decision.policy_interval_days,
                expected["policyIntervalDays"],
                "exact",
            ),
            (
                "intervalDays",
                decision.interval_days,
                expected["intervalDays"],
                "exact",
            ),
            (
                "lapsesDelta",
                decision.lapses_delta,
                expected["lapsesDelta"],
                "exact",
            ),
        ]

        mismatches = []
        for name, actual, wanted, mode in checks:
            if mode == "close":
                ok = _close(actual, wanted, tolerance)
            else:
                ok = actual == wanted
            if not ok:
                mismatches.append(f"{name}: actual={actual!r} expected={wanted!r}")

        if mismatches:
            failures += 1
            print(f"FAIL {vector_id}  {vector['description']}")
            for mismatch in mismatches:
                print(f"     - {mismatch}")
        else:
            print(f"PASS {vector_id}  {vector['description']}")

    print()
    if failures:
        print(f"FAILED: {failures} of {len(payload['vectors'])} vectors")
        return 1

    print(f"OK: {len(payload['vectors'])} vectors passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
