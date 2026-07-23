from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Callable, Iterable

MIN_TRAIN = 8
MIN_VALIDATION = 3
MIN_TEST = 3


def number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def nested(mapping: object, *keys: str) -> object:
    current = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


@dataclass(frozen=True)
class Row:
    symbol: str
    timeframe: str
    decision_time: datetime
    strategy: str
    direction: str
    source: str
    actionability: str
    setup_validity: str
    activation_type: str
    geometry_lane: str
    measured_geometry_lane: str
    measured_geometry_passed: bool | None
    higher_timeframe_conflict: bool | None
    immediate_timeframe_conflict: bool | None
    entry_confirmation_complete: bool | None
    setup_direction_confirmed: bool | None
    confidence: float | None
    expected_r: float | None
    cost_drag_pct: float | None
    stop_distance_pct: float | None
    target_quality: float | None
    realized_r: float
    event_key: str


@dataclass(frozen=True)
class Condition:
    name: str
    predicate: Callable[[Row], bool]


def load_rows(report_dir: Path) -> list[Row]:
    raw: list[Row] = []
    for path in sorted(report_dir.glob("*.json")):
        payload = json.loads(path.read_text())
        symbol = str(payload.get("symbol") or "unknown")
        timeframe = str(payload.get("replay_timeframe") or "unknown")
        trades = nested(payload, "shadow_replay", "trades")
        if not isinstance(trades, list):
            continue
        for trade in trades:
            if not isinstance(trade, dict):
                continue
            signal = trade.get("signal") if isinstance(trade.get("signal"), dict) else {}
            metadata = trade.get("metadata") if isinstance(trade.get("metadata"), dict) else {}
            diagnostics = signal.get("diagnostics") if isinstance(signal.get("diagnostics"), dict) else {}
            confirmation = diagnostics.get("confirmation") if isinstance(diagnostics.get("confirmation"), dict) else {}
            geometry = diagnostics.get("geometry_audit") if isinstance(diagnostics.get("geometry_audit"), dict) else {}
            realized = number(trade.get("realized_r_multiple"))
            decision_time = parse_time(trade.get("decision_time") or signal.get("generated_at"))
            if realized is None or decision_time is None:
                continue
            event_key = str(trade.get("recovery_event_id") or trade.get("opportunity_id") or "")
            if not event_key:
                event_key = "|".join(
                    [
                        symbol,
                        timeframe,
                        str(signal.get("strategy") or "unknown"),
                        str(signal.get("direction") or "unknown"),
                        decision_time.isoformat(),
                        str(metadata.get("candidate_id") or signal.get("candidate_id") or ""),
                    ]
                )
            raw.append(
                Row(
                    symbol=symbol,
                    timeframe=timeframe,
                    decision_time=decision_time,
                    strategy=str(signal.get("strategy") or "unknown"),
                    direction=str(signal.get("direction") or "unknown"),
                    source=str(metadata.get("replay_source") or trade.get("replay_reason_code") or "unknown"),
                    actionability=str(trade.get("actionability_state") or "unknown"),
                    setup_validity=str(metadata.get("setup_validity") or "unknown"),
                    activation_type=str(signal.get("activation_type") or "unknown"),
                    geometry_lane=str(diagnostics.get("geometry_lane") or "unknown"),
                    measured_geometry_lane=str(diagnostics.get("measured_geometry_lane") or "unknown"),
                    measured_geometry_passed=(
                        diagnostics.get("measured_geometry_passed")
                        if isinstance(diagnostics.get("measured_geometry_passed"), bool)
                        else None
                    ),
                    higher_timeframe_conflict=(
                        confirmation.get("higher_timeframe_conflict")
                        if isinstance(confirmation.get("higher_timeframe_conflict"), bool)
                        else None
                    ),
                    immediate_timeframe_conflict=(
                        confirmation.get("immediate_timeframe_conflict")
                        if isinstance(confirmation.get("immediate_timeframe_conflict"), bool)
                        else None
                    ),
                    entry_confirmation_complete=(
                        confirmation.get("entry_confirmation_complete")
                        if isinstance(confirmation.get("entry_confirmation_complete"), bool)
                        else None
                    ),
                    setup_direction_confirmed=(
                        confirmation.get("setup_direction_confirmed")
                        if isinstance(confirmation.get("setup_direction_confirmed"), bool)
                        else None
                    ),
                    confidence=number(signal.get("confidence_score")),
                    expected_r=number(metadata.get("expected_r")),
                    cost_drag_pct=number(geometry.get("cost_drag_on_reward_pct")),
                    stop_distance_pct=number(geometry.get("stop_distance_pct")),
                    target_quality=number(geometry.get("target_quality")),
                    realized_r=realized,
                    event_key=event_key,
                )
            )

    exact: dict[str, Row] = {}
    for row in sorted(raw, key=lambda item: (item.decision_time, item.symbol, item.timeframe)):
        exact.setdefault(row.event_key, row)

    episodes: dict[tuple[str, str, str, int], Row] = {}
    for row in exact.values():
        bucket = int(row.decision_time.timestamp()) // (15 * 60)
        key = (row.symbol, row.strategy, row.direction, bucket)
        episodes.setdefault(key, row)
    return sorted(episodes.values(), key=lambda item: item.decision_time)


def metrics(rows: list[Row]) -> dict[str, float | int | None]:
    values = [row.realized_r for row in rows]
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    return {
        "samples": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(values) * 100.0 if values else None,
        "total_r": sum(values),
        "average_r": sum(values) / len(values) if values else None,
        "profit_factor": gross_win / gross_loss if gross_loss else (float("inf") if gross_win else None),
    }


def split(rows: list[Row]) -> tuple[list[Row], list[Row], list[Row]]:
    count = len(rows)
    train_end = max(1, int(count * 0.60))
    validation_end = max(train_end + 1, int(count * 0.80))
    return rows[:train_end], rows[train_end:validation_end], rows[validation_end:]


def categorical_conditions(rows: list[Row]) -> list[Condition]:
    attributes = (
        "timeframe",
        "strategy",
        "direction",
        "source",
        "actionability",
        "setup_validity",
        "activation_type",
        "geometry_lane",
        "measured_geometry_lane",
    )
    conditions: list[Condition] = []
    for attribute in attributes:
        for value in sorted({str(getattr(row, attribute)) for row in rows}):
            if value == "unknown":
                continue
            conditions.append(
                Condition(
                    f"{attribute}={value}",
                    lambda row, attribute=attribute, value=value: str(getattr(row, attribute)) == value,
                )
            )
    for attribute in (
        "measured_geometry_passed",
        "higher_timeframe_conflict",
        "immediate_timeframe_conflict",
        "entry_confirmation_complete",
        "setup_direction_confirmed",
    ):
        for value in (True, False):
            conditions.append(
                Condition(
                    f"{attribute}={value}",
                    lambda row, attribute=attribute, value=value: getattr(row, attribute) is value,
                )
            )
    return conditions


def numeric_conditions() -> list[Condition]:
    specs = {
        "confidence": (40.0, 50.0, 60.0, 70.0),
        "expected_r": (0.30, 0.60, 1.00, 1.50),
        "cost_drag_pct": (10.0, 20.0, 30.0, 40.0),
        "stop_distance_pct": (0.25, 0.50, 1.00, 2.00),
        "target_quality": (50.0, 60.0, 70.0, 80.0),
    }
    conditions: list[Condition] = []
    for attribute, thresholds in specs.items():
        for threshold in thresholds:
            conditions.append(
                Condition(
                    f"{attribute}>={threshold}",
                    lambda row, attribute=attribute, threshold=threshold: (
                        getattr(row, attribute) is not None and getattr(row, attribute) >= threshold
                    ),
                )
            )
            if attribute in {"cost_drag_pct", "stop_distance_pct"}:
                conditions.append(
                    Condition(
                        f"{attribute}<={threshold}",
                        lambda row, attribute=attribute, threshold=threshold: (
                            getattr(row, attribute) is not None and getattr(row, attribute) <= threshold
                        ),
                    )
                )
    return conditions


def apply(rows: Iterable[Row], conditions: tuple[Condition, ...]) -> list[Row]:
    return [row for row in rows if all(condition.predicate(row) for condition in conditions)]


def positive(result: dict[str, float | int | None], minimum: int) -> bool:
    return int(result["samples"] or 0) >= minimum and float(result["total_r"] or 0.0) > 0.0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover pre-outcome profitable lanes with chronological holdouts."
    )
    parser.add_argument("report_dir", type=Path)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    rows = load_rows(args.report_dir)
    train, validation, test = split(rows)
    print("=" * 78)
    print("APEX 11D.6G — PROFITABLE LANE DISCOVERY")
    print("=" * 78)
    print(f"Unique cross-TF episodes : {len(rows)}")
    print(f"Train / validation / test: {len(train)} / {len(validation)} / {len(test)}")
    print(f"Baseline train           : {metrics(train)}")
    print(f"Baseline validation      : {metrics(validation)}")
    print(f"Baseline test            : {metrics(test)}")
    print()

    available = categorical_conditions(train) + numeric_conditions()
    candidates: list[
        tuple[float, tuple[Condition, ...], dict[str, Any], dict[str, Any], dict[str, Any]]
    ] = []
    for width in (1, 2, 3):
        for combo in combinations(available, width):
            train_metrics = metrics(apply(train, combo))
            if not positive(train_metrics, MIN_TRAIN):
                continue
            validation_metrics = metrics(apply(validation, combo))
            if not positive(validation_metrics, MIN_VALIDATION):
                continue
            test_metrics = metrics(apply(test, combo))
            score = float(validation_metrics["total_r"] or 0.0) + float(
                validation_metrics["average_r"] or 0.0
            )
            candidates.append((score, combo, train_metrics, validation_metrics, test_metrics))

    candidates.sort(key=lambda item: item[0], reverse=True)
    print("HOLDOUT-CONSISTENT LANES")
    if not candidates:
        print("  None passed positive train and validation gates.")
    for index, (_, combo, train_metrics, validation_metrics, test_metrics) in enumerate(
        candidates[: args.top], 1
    ):
        names = " AND ".join(condition.name for condition in combo)
        print(f"\n#{index} {names}")
        print(f"  train      : {train_metrics}")
        print(f"  validation : {validation_metrics}")
        print(f"  test       : {test_metrics}")
        approved = (
            int(test_metrics["samples"] or 0) >= MIN_TEST
            and float(test_metrics["total_r"] or 0.0) > 0.0
            and float(test_metrics["profit_factor"] or 0.0) >= 1.20
        )
        print(f"  unseen gate: {'PASS' if approved else 'FAIL'}")

    approved_count = sum(
        int(test_metrics["samples"] or 0) >= MIN_TEST
        and float(test_metrics["total_r"] or 0.0) > 0.0
        and float(test_metrics["profit_factor"] or 0.0) >= 1.20
        for _, _, _, _, test_metrics in candidates
    )
    print()
    print("DECISION")
    if approved_count:
        print(f"  {approved_count} lane(s) passed the small unseen-sample gate.")
        print("  Keep experimental; require 30+ unseen trades before production activation.")
    else:
        print("  No lane passed the unseen-sample gate.")
        print("  Do not loosen production gates from this dataset.")


if __name__ == "__main__":
    main()
