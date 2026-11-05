"""Reference implementation of the RPE FSRS-3 policy.

This module is intentionally dependency-free. It implements the normative
formulas in docs/01-复习规划引擎-业务描述-v0.2.md §7.4.1, plus the
business-layer due-date overrides in §7.4 POLICY-006c.

It is a conformance reference, not the engine. Daily planning, queues,
same-day repeats, and persistence live in the engine and are deliberately
out of scope here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Optional, Sequence, Tuple

Rating = Literal["forgot", "vague", "know", "known"]

FSRS3_DEFAULT_WEIGHTS: Tuple[float, ...] = (
    0.9605,
    1.7234,
    4.8527,
    -1.1917,
    -1.2956,
    0.0573,
    1.7352,
    -0.1673,
    1.065,
    1.8907,
    -0.3832,
    0.5867,
    1.0721,
)

S_MIN = 0.01
S_MAX = 36500.0
D_MIN = 1.0
D_MAX = 10.0

GRADE = {
    "forgot": 1,  # Again
    "vague": 2,   # Hard
    "know": 3,    # Good
}


@dataclass(frozen=True)
class MemoryState:
    stability_days: float
    difficulty: float


@dataclass(frozen=True)
class Decision:
    state: Optional[MemoryState]
    retrievability: Optional[float]
    policy_interval_days: Optional[int]
    interval_days: Optional[int]
    lapses_delta: int = 0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _round_half_up(value: float) -> int:
    """Match JavaScript Math.round for positive values."""
    return math.floor(value + 0.5)


def forgetting_curve(elapsed_days: float, stability_days: float) -> float:
    return 0.9 ** (elapsed_days / stability_days)


def initial_stability(grade: int, weights: Sequence[float] = FSRS3_DEFAULT_WEIGHTS) -> float:
    return _clamp(weights[0] + (grade - 1) * weights[1], S_MIN, S_MAX)


def initial_difficulty(grade: int, weights: Sequence[float] = FSRS3_DEFAULT_WEIGHTS) -> float:
    return _clamp(weights[2] + (grade - 3) * weights[3], D_MIN, D_MAX)


def next_difficulty(
    difficulty: float,
    grade: int,
    weights: Sequence[float] = FSRS3_DEFAULT_WEIGHTS,
) -> float:
    next_d = difficulty + weights[4] * (grade - 3)
    reverted = weights[5] * initial_difficulty(3, weights) + (1 - weights[5]) * next_d
    return _clamp(reverted, D_MIN, D_MAX)


def next_recall_stability(
    difficulty: float,
    stability: float,
    retrievability: float,
    weights: Sequence[float] = FSRS3_DEFAULT_WEIGHTS,
) -> float:
    value = stability * (
        1
        + math.exp(weights[6])
        * (11 - difficulty)
        * stability ** weights[7]
        * (math.exp((1 - retrievability) * weights[8]) - 1)
    )
    return _clamp(value, S_MIN, S_MAX)


def next_forget_stability(
    difficulty: float,
    stability: float,
    retrievability: float,
    weights: Sequence[float] = FSRS3_DEFAULT_WEIGHTS,
) -> float:
    value = (
        weights[9]
        * difficulty ** weights[10]
        * stability ** weights[11]
        * math.exp((1 - retrievability) * weights[12])
    )
    return _clamp(value, S_MIN, S_MAX)


def next_interval(
    stability_days: float,
    target_retention: float = 0.9,
    max_interval_days: int = 365,
) -> int:
    if not 0 < target_retention <= 1:
        raise ValueError("target_retention must be in (0, 1]")
    raw = stability_days * math.log(target_retention) / math.log(0.9)
    return min(max(1, _round_half_up(raw)), max_interval_days)


def schedule(
    state: Optional[MemoryState],
    rating: Rating,
    elapsed_days: float,
    *,
    target_retention: float = 0.9,
    max_interval_days: int = 365,
    vague_max_interval_days: Optional[int] = 3,
    weights: Sequence[float] = FSRS3_DEFAULT_WEIGHTS,
) -> Decision:
    """Apply one valid long-term rating.

    The caller must only pass the first scheduled rating of a study day.
    Same-day repeats, today/history review, and free review must not call
    this function (see POLICY-006b).
    """

    if len(weights) != 13:
        raise ValueError(f"FSRS-3 requires 13 weights, got {len(weights)}")

    if rating == "known":
        return Decision(
            state=None,
            retrievability=None,
            policy_interval_days=None,
            interval_days=None,
            lapses_delta=0,
        )

    if rating not in GRADE:
        raise ValueError(f"unknown rating: {rating}")

    grade = GRADE[rating]

    if state is None:
        stability = initial_stability(grade, weights)
        difficulty = initial_difficulty(grade, weights)
        retrievability = None
    else:
        old_stability = state.stability_days
        retrievability = forgetting_curve(elapsed_days, old_stability)
        difficulty = next_difficulty(state.difficulty, grade, weights)
        if grade == 1:
            stability = next_forget_stability(
                difficulty, old_stability, retrievability, weights
            )
        else:
            stability = next_recall_stability(
                difficulty, old_stability, retrievability, weights
            )

    policy_interval = next_interval(
        stability, target_retention, max_interval_days
    )

    lapses_delta = 0
    if rating == "forgot":
        interval = 1  # SCHED-004
        lapses_delta = 1
    elif rating == "vague":
        interval = (
            policy_interval
            if vague_max_interval_days is None
            else min(policy_interval, vague_max_interval_days)
        )
    else:
        interval = policy_interval

    return Decision(
        state=MemoryState(stability_days=stability, difficulty=difficulty),
        retrievability=retrievability,
        policy_interval_days=policy_interval,
        interval_days=interval,
        lapses_delta=lapses_delta,
    )
