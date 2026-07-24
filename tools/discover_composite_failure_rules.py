#!/usr/bin/env python3
"""Discover leakage-safe composite rules while avoiding raw price-scale artifacts."""

from __future__ import annotations

import argparse
import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path

MIN_WINNER_RETENTION = 0.90
MIN_SEVERE_CAPTURE = 0.10
EXCLUDED_KEYS = {
    "decision_entry_price",
    "decision_stop_price",
    "decision_target_price",
    "decision_generated_at",
    "decision_feature_count",
}


@dataclass(frozen=True)
class Row:
    source: str
    outcome: str
    severe: bool
    metadata: dict[str, object]


def num(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float) and math.isfinite(float(value)):
        return float(value)
    return None


def load(path: Path) -> list[Row]:
    data = json.loads(path.read_text(encoding="utf-8"))
    trades = data.get("shadow_replay", {}).get("trades", [])
    rows: list[Row] = []
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        outcome = str(trade.get("outcome", "")).lower()
        metadata = trade.get("metadata", {})
        if outcome not in {"target", "stop"} or not isinstance(metadata, dict):
            continue
        rows.append(
            Row(
                source=path.stem,
                outcome=outcome,
                severe=outcome == "stop" and metadata.get("deep_directional_failure") is True,
                metadata=metadata,
            )
        )
    return rows


def cuts(values: list[float]) -> list[float]:
    ordered = sorted(set(values))
    if len(ordered) < 5:
        return []
    indexes = {
        len(ordered) // 5,
        len(ordered) // 3,
        len(ordered) // 2,
        (2 * len(ordered)) // 3,
        (4 * len(ordered)) // 5,
    }
    return [ordered[index] for index in sorted(indexes)]


def metrics(rows: list[Row], predicate) -> dict[str, float | int | dict[str, float]]:
    wins = [row for row in rows if row.outcome == "target"]
    stops = [row for row in rows if row.outcome == "stop"]
    severe = [row for row in rows if row.severe]
    blocked = [row for row in rows if predicate(row)]
    blocked_wins = sum(row.outcome == "target" for row in blocked)
    blocked_stops = sum(row.outcome == "stop" for row in blocked)
    blocked_severe = sum(row.severe for row in blocked)
    retained_wins = len(wins) - blocked_wins
    retained_stops = len(stops) - blocked_stops
    per_source: dict[str, float] = {}
    for source in sorted({row.source for row in rows}):
        source_severe = [row for row in severe if row.source == source]
        source_blocked = [row for row in source_severe if predicate(row)]
        per_source[source] = len(source_blocked) / len(source_severe) if source_severe else 0.0
    baseline = len(wins) / (len(wins) + len(stops)) if wins or stops else 0.0
    filtered = (
        retained_wins / (retained_wins + retained_stops) if retained_wins + retained_stops else 0.0
    )
    return {
        "winner_retention": retained_wins / len(wins) if wins else 0.0,
        "loss_removal": blocked_stops / len(stops) if stops else 0.0,
        "severe_capture": blocked_severe / len(severe) if severe else 0.0,
        "blocked_wins": blocked_wins,
        "blocked_stops": blocked_stops,
        "blocked_severe": blocked_severe,
        "baseline_win_rate": baseline,
        "filtered_win_rate": filtered,
        "per_source_capture": per_source,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    rows = [row for path in args.paths for row in load(path)]
    keys = sorted(
        {
            key
            for row in rows
            for key, value in row.metadata.items()
            if key.startswith("decision_") and key not in EXCLUDED_KEYS and num(value) is not None
        }
    )

    candidates: list[tuple[str, str, float]] = []
    for key in keys:
        values = [value for row in rows if (value := num(row.metadata.get(key))) is not None]
        for cut in cuts(values):
            candidates.append((key, ">=", cut))
            candidates.append((key, "<=", cut))

    def matches(row: Row, rule: tuple[str, str, float]) -> bool:
        key, op, cut = rule
        value = num(row.metadata.get(key))
        if value is None:
            return False
        return value >= cut if op == ">=" else value <= cut

    results: list[tuple[float, str, dict[str, object]]] = []
    for left, right in itertools.combinations(candidates, 2):
        if left[0] == right[0]:
            continue
        report = metrics(rows, lambda row, a=left, b=right: matches(row, a) and matches(row, b))
        retention = float(report["winner_retention"])
        capture = float(report["severe_capture"])
        per_source = report["per_source_capture"]
        assert isinstance(per_source, dict)
        consistent = sum(value > 0.0 for value in per_source.values()) >= 2
        if (
            retention >= MIN_WINNER_RETENTION
            and capture >= MIN_SEVERE_CAPTURE
            and int(report["blocked_severe"]) >= 3
            and consistent
        ):
            uplift = float(report["filtered_win_rate"]) - float(report["baseline_win_rate"])
            score = capture * 4 + float(report["loss_removal"]) * 2 + max(0.0, uplift)
            text = f"{left[0]} {left[1]} {left[2]:.6g} AND {right[0]} {right[1]} {right[2]:.6g}"
            results.append((score, text, report))

    results.sort(reverse=True)
    print(f"resolved rows: {len(rows)}")
    print("raw price fields excluded")
    print("requires capture in at least two sources")
    for index, (_, text, report) in enumerate(results[: args.top], start=1):
        print(f"\n#{index:02d} {text}")
        print(
            f"winner retention: {float(report['winner_retention']):.2%} | "
            f"severe capture: {float(report['severe_capture']):.2%} | "
            f"loss removal: {float(report['loss_removal']):.2%} | "
            f"blocked winners: {int(report['blocked_wins'])} | "
            f"win rate: {float(report['baseline_win_rate']):.2%} -> "
            f"{float(report['filtered_win_rate']):.2%} | "
            f"per-source: {report['per_source_capture']}"
        )


if __name__ == "__main__":
    main()
