#!/usr/bin/env python3
"""Find leakage-safe decision thresholds that preserve winners."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

MIN_WINNER_RETENTION = 0.90
MIN_CAPTURE = 0.10


@dataclass(frozen=True)
class Row:
    source: str
    outcome: str
    severe_loss: bool
    metadata: dict[str, object]


def number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float) and math.isfinite(float(value)):
        return float(value)
    return None


def load_rows(path: Path) -> list[Row]:
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
                severe_loss=(
                    outcome == "stop" and metadata.get("deep_directional_failure") is True
                ),
                metadata=metadata,
            )
        )
    return rows


def thresholds(values: list[float]) -> list[float]:
    ordered = sorted(set(values))
    if len(ordered) < 3:
        return []
    indexes = {
        0,
        len(ordered) // 10,
        len(ordered) // 4,
        len(ordered) // 3,
        len(ordered) // 2,
        (2 * len(ordered)) // 3,
        (3 * len(ordered)) // 4,
        (9 * len(ordered)) // 10,
        len(ordered) - 1,
    }
    return [ordered[min(index, len(ordered) - 1)] for index in sorted(indexes)]


def evaluate(rows: list[Row], key: str, op: str, threshold: float) -> dict[str, float | int]:
    wins = [row for row in rows if row.outcome == "target"]
    stops = [row for row in rows if row.outcome == "stop"]
    severe = [row for row in rows if row.severe_loss]

    def matches(row: Row) -> bool:
        value = number(row.metadata.get(key))
        if value is None:
            return False
        return value >= threshold if op == ">=" else value <= threshold

    blocked = [row for row in rows if matches(row)]
    blocked_wins = sum(row.outcome == "target" for row in blocked)
    blocked_stops = sum(row.outcome == "stop" for row in blocked)
    blocked_severe = sum(row.severe_loss for row in blocked)
    retained_wins = len(wins) - blocked_wins
    retained_stops = len(stops) - blocked_stops
    baseline_total = len(wins) + len(stops)
    filtered_total = retained_wins + retained_stops
    return {
        "blocked_wins": blocked_wins,
        "blocked_stops": blocked_stops,
        "blocked_severe": blocked_severe,
        "winner_retention": retained_wins / len(wins) if wins else 0.0,
        "loss_removal": blocked_stops / len(stops) if stops else 0.0,
        "severe_capture": blocked_severe / len(severe) if severe else 0.0,
        "baseline_win_rate": len(wins) / baseline_total if baseline_total else 0.0,
        "filtered_win_rate": retained_wins / filtered_total if filtered_total else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    rows = [row for path in args.paths for row in load_rows(path)]
    keys = sorted(
        {
            key
            for row in rows
            for key, value in row.metadata.items()
            if key.startswith("decision_") and number(value) is not None
        }
    )

    results: list[tuple[float, str, str, float, dict[str, float | int]]] = []
    for key in keys:
        values = [value for row in rows if (value := number(row.metadata.get(key))) is not None]
        for threshold in thresholds(values):
            for op in (">=", "<="):
                metrics = evaluate(rows, key, op, threshold)
                if (
                    float(metrics["winner_retention"]) >= MIN_WINNER_RETENTION
                    and float(metrics["severe_capture"]) >= MIN_CAPTURE
                    and int(metrics["blocked_severe"]) >= 3
                ):
                    score = (
                        float(metrics["severe_capture"]) * 4
                        + float(metrics["loss_removal"]) * 2
                        + max(
                            0.0,
                            float(metrics["filtered_win_rate"])
                            - float(metrics["baseline_win_rate"]),
                        )
                    )
                    results.append((score, key, op, threshold, metrics))

    results.sort(reverse=True)
    print(f"resolved rows: {len(rows)}")
    print("sources:", sorted({row.source for row in rows}))
    print("guardrail: winner retention >= 90%")
    for rank, (_, key, op, threshold, metrics) in enumerate(results[: args.top], start=1):
        print(f"\n#{rank:02d} {key} {op} {threshold:.6g}")
        print(
            f"winner retention: {float(metrics['winner_retention']):.2%} | "
            f"severe capture: {float(metrics['severe_capture']):.2%} | "
            f"loss removal: {float(metrics['loss_removal']):.2%} | "
            f"blocked winners: {int(metrics['blocked_wins'])} | "
            f"win rate: {float(metrics['baseline_win_rate']):.2%} -> "
            f"{float(metrics['filtered_win_rate']):.2%}"
        )


if __name__ == "__main__":
    main()
