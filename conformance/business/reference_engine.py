"""Minimal, non-production reference engine for RPE v0.3 business conformance.

This engine implements only the rules exercised by `scenarios.json`:
- lifecycle / phase separation
- one long-term update per item per study day
- `scheduled` and `extra` state-updating contexts
- TP1 test strategy (not FSRS-3)
- merged / split daily allocation
- fill mode with advanced items
- same-day queue reinsertion
- command idempotency

It is intentionally small. It is not a reference implementation of FSRS-3;
see ../fsrs3_reference.py for that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import floor
from typing import Any, Optional

RATINGS = {"know", "vague", "forgot"}
STATEFUL_CONTEXTS = {"scheduled", "extra"}

INITIAL_STABILITY = {"know": 10.0, "vague": 3.0, "forgot": 1.0}
STABILITY_MULTIPLIER = {"know": 2.0, "vague": 1.2, "forgot": 1.0}


def round_half_up(value: float) -> int:
    return int(floor(value + 0.5))


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


@dataclass
class Item:
    item_id: str
    lifecycle: str = "queued"
    stability: Optional[float] = None
    difficulty: Optional[float] = None
    due_day: Optional[int] = None
    last_review_day: Optional[int] = None
    last_interval_days: Optional[int] = None
    reps: int = 0
    lapses: int = 0
    first_learned_day: Optional[int] = None
    known_snapshot: Optional[dict[str, Any]] = None
    epoch: int = 1


@dataclass
class Engine:
    config: dict[str, Any]
    items: dict[str, Item] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    processed: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add_item(self, item: Item) -> None:
        self.items[item.item_id] = item

    def _first_stateful_today(self, item_id: str, day_key: int) -> bool:
        for event in self.events:
            if (
                event["itemId"] == item_id
                and event["dayKey"] == day_key
                and event.get("eventType") == "study_rated"
                and event.get("context") in STATEFUL_CONTEXTS
                and not event.get("sameDayRepeat", False)
            ):
                return False
        return True

    def rate(
        self,
        item_id: str,
        rating: str,
        day_key: int,
        context: str = "scheduled",
        command_id: Optional[str] = None,
        was_new: Optional[bool] = None,
    ) -> dict[str, Any]:
        if command_id and command_id in self.processed:
            return self.processed[command_id]

        item = self.items.get(item_id)
        if item is None:
            raise ValueError(f"ITEM_NOT_FOUND: {item_id}")
        if item.lifecycle == "deleted":
            raise ValueError(f"ITEM_NOT_ACTIVE: {item_id}")
        if rating not in RATINGS and rating != "known":
            raise ValueError(f"INVALID_RATING: {rating}")

        if was_new is None:
            was_new = item.lifecycle == "queued"

        if rating == "known":
            item.known_snapshot = {
                "memory": (
                    None
                    if item.stability is None
                    else {
                        "stabilityDays": item.stability,
                        "difficulty": item.difficulty,
                    }
                ),
                "schedule": {
                    "dueDay": item.due_day,
                    "lastReviewDay": item.last_review_day,
                    "lastIntervalDays": item.last_interval_days,
                },
            }
            item.lifecycle = "known"
            item.due_day = None
            event = self._event(
                item_id, day_key, "marked_known", None, None, command_id
            )
            self.events.append(event)
            if command_id:
                self.processed[command_id] = event
            return event

        stateful = context in STATEFUL_CONTEXTS
        first_today = stateful and self._first_stateful_today(item_id, day_key)

        if not stateful or not first_today:
            event = self._event(
                item_id,
                day_key,
                "study_rated",
                context,
                rating,
                command_id,
                same_day_repeat=stateful and not first_today,
                was_new=was_new,
            )
            self.events.append(event)
            if command_id:
                self.processed[command_id] = event
            return event

        old_stability = item.stability
        if old_stability is None:
            stability = INITIAL_STABILITY[rating]
            difficulty = 5.0
        else:
            stability = old_stability * STABILITY_MULTIPLIER[rating]
            difficulty = item.difficulty if item.difficulty is not None else 5.0

        interval = clamp(
            round_half_up(stability),
            int(self.config["minIntervalDays"]),
            int(self.config["maxIntervalDays"]),
        )

        if rating == "forgot" and self.config["forgotNextDay"]:
            interval = 1
        if rating == "vague" and self.config["vagueMaxIntervalDays"] is not None:
            interval = min(interval, int(self.config["vagueMaxIntervalDays"]))

        item.lifecycle = "active"
        item.stability = stability
        item.difficulty = difficulty
        item.due_day = day_key + interval
        item.last_review_day = day_key
        item.last_interval_days = interval
        item.reps += 1
        if rating == "forgot":
            item.lapses += 1
        if item.first_learned_day is None:
            item.first_learned_day = day_key

        event = self._event(
            item_id,
            day_key,
            "study_rated",
            context,
            rating,
            command_id,
            interval_after=interval,
            stability=stability,
            difficulty=difficulty,
            was_new=was_new,
        )
        self.events.append(event)
        if command_id:
            self.processed[command_id] = event
        return event

    def _event(
        self,
        item_id: str,
        day_key: int,
        event_type: str,
        context: Optional[str],
        rating: Optional[str],
        command_id: Optional[str],
        *,
        same_day_repeat: bool = False,
        interval_after: Optional[int] = None,
        stability: Optional[float] = None,
        difficulty: Optional[float] = None,
        was_new: bool = False,
    ) -> dict[str, Any]:
        return {
            "eventId": f"evt_{len(self.events) + 1}",
            "commandId": command_id or f"cmd_{len(self.events) + 1}",
            "itemId": item_id,
            "dayKey": day_key,
            "eventType": event_type,
            "context": context,
            "rating": rating,
            "sameDayRepeat": same_day_repeat,
            "intervalAfter": interval_after,
            "stabilityDays": stability,
            "difficulty": difficulty,
            "wasNew": was_new,
        }

    def plan(self, today: int) -> dict[str, Any]:
        review_pool = sorted(
            [
                item
                for item in self.items.values()
                if item.lifecycle == "active"
                and item.due_day is not None
                and item.due_day <= today
            ],
            key=lambda item: (item.due_day, item.item_id),
        )
        future_pool = sorted(
            [
                item
                for item in self.items.values()
                if item.lifecycle == "active"
                and item.due_day is not None
                and item.due_day > today
            ],
            key=lambda item: (item.due_day, item.item_id),
        )
        new_pool = sorted(
            [item for item in self.items.values() if item.lifecycle == "queued"],
            key=lambda item: item.item_id,
        )

        done = [
            event
            for event in self.events
            if event["dayKey"] == today
            and event["eventType"] == "study_rated"
            and event.get("context") == "scheduled"
            and not event.get("sameDayRepeat", False)
        ]
        done_ids = {event["itemId"] for event in done}
        done_new = {event["itemId"] for event in done if event.get("wasNew")}
        done_review = done_ids - done_new

        if self.config["volumeMode"] == "merged":
            remaining = max(0, int(self.config["dailyStudyAmount"]) - len(done_ids))
            review_target = min(len(review_pool), remaining)
            review_items = review_pool[:review_target]
            advanced: list[Item] = []
            if (
                self.config.get("reviewFillMode") == "fill"
                and review_target < remaining
            ):
                need = remaining - review_target
                advanced = future_pool[:need]
                review_items = review_items + advanced
                review_target = len(review_items)
            max_new = self.config.get("maxNewPerDay")
            new_limit = remaining - review_target
            if max_new is not None:
                new_limit = min(new_limit, int(max_new))
            new_target = min(len(new_pool), max(0, new_limit))
            new_items = new_pool[:new_target]
        else:
            remaining_review = max(
                0, int(self.config["dailyReviewQuota"]) - len(done_review)
            )
            remaining_new = max(
                0, int(self.config["dailyNewQuota"]) - len(done_new)
            )
            if (
                self.config.get("newWordsBlockedByBacklog")
                and len(review_pool) > remaining_review
            ):
                remaining_new = 0
            review_target = min(len(review_pool), remaining_review)
            review_items = review_pool[:review_target]
            advanced = []
            max_new = self.config.get("maxNewPerDay")
            if max_new is not None:
                remaining_new = min(remaining_new, int(max_new))
            new_target = min(len(new_pool), remaining_new)
            new_items = new_pool[:new_target]

        return {
            "reviewTarget": review_target,
            "newTarget": new_target,
            "reviewIds": [item.item_id for item in review_items],
            "newIds": [item.item_id for item in new_items],
            "advancedIds": [item.item_id for item in advanced],
        }

    def item_view(self, item_id: str) -> dict[str, Any]:
        item = self.items[item_id]
        return {
            "lifecycle": item.lifecycle,
            "dueDay": item.due_day,
            "reps": item.reps,
            "lapses": item.lapses,
            "stabilityDays": item.stability,
            "difficulty": item.difficulty,
            "lastReviewDay": item.last_review_day,
            "epoch": item.epoch,
        }


def queue_after_reinsert(
    queue: list[str], current_id: str, gap: Optional[int]
) -> list[str]:
    rest = [item_id for item_id in queue if item_id != current_id]
    if gap is None:
        return rest + [current_id]
    index = min(gap, len(rest))
    return rest[:index] + [current_id] + rest[index:]
