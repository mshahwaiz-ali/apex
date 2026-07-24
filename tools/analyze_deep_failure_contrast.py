#!/usr/bin/env python3
"""Compare pre-entry metadata across winners, normal stops, and deep failures."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

IGNORED_PREFIXES = (
    "post_stop_",
    "shared_sweep_reclaim_",
    "deep_directional_failure",
    "recovery_",
    "sweep_reclaim_",
    "retest_",
)
IGNORED_KEYS = {
    "stop_hit",
    "outcome",
    "first_exit_event",
    "terminal_state",
    "maximum_favorable_excursion_r",
    "maximum_adverse_excursion_r",
    "counterfactual_path_mfe_r",
    "counterfactual_path_mae_r",
    "direction_correct_at_horizon",
}


def _trades(report: dict[str, Any]) -> list[dict[str, Any]]:
    replay = report.get("shadow_replay", {})
    trades = replay.get("trades", [])
    return trades if isinstance(trades, list) else []


def _group(trade: dict[str, Any]) -> str | None:
    outcome = str(trade.get("outcome", "")).lower()
    metadata = trade.get("metadata", {})
    if not isinstance(metadata, dict):
        return None
    if outcome == "target":
        return "winner"
    if outcome != "stop":
        return None
    if metadata.get("deep_directional_failure") is True:
        return "deep_failure"
    return "normal_stop"


def _eligible(key: str, value: object) -> bool:
    if key in IGNORED_KEYS or key.startswith(IGNORED_PREFIXES):
        return False
    if value is None or isinstance(value, dict | list | tuple):
        return False
    return isinstance(value, bool | int | float | str)


def _numeric(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float) and math.isfinite(float(value)):
        return float(value)
    return None


def analyze(path: Path) -> None:
    report = json.loads(path.read_text(encoding="utf-8"))
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for trade in _trades(report):
        group = _group(trade)
        metadata = trade.get("metadata", {})
        if group is not None and isinstance(metadata, dict):
            groups[group].append(metadata)

    print(f"\n{'=' * 96}\n{path.name}\n{'=' * 96}")
    print("group sizes:", {name: len(rows) for name, rows in groups.items()})

    keys = sorted(
        {
            key
            for rows in groups.values()
            for row in rows
            for key, value in row.items()
            if _eligible(key, value)
        }
    )

    numeric_rows: list[tuple[float, str, dict[str, float]]] = []
    categorical_rows: list[tuple[float, str, dict[str, str]]] = []

    for key in keys:
        numeric_summary: dict[str, float] = {}
        numeric_counts: dict[str, int] = {}
        for name, rows in groups.items():
            values = [_numeric(row.get(key)) for row in rows]
            clean = [value for value in values if value is not None]
            if clean:
                numeric_summary[name] = sum(clean) / len(clean)
                numeric_counts[name] = len(clean)
        if "winner" in numeric_summary and "deep_failure" in numeric_summary:
            winner = numeric_summary["winner"]
            deep = numeric_summary["deep_failure"]
            scale = max(abs(winner), abs(deep), 1e-9)
            separation = abs(deep - winner) / scale
            if min(numeric_counts["winner"], numeric_counts["deep_failure"]) >= 3:
                numeric_rows.append((separation, key, numeric_summary))
            continue

        category_summary: dict[str, str] = {}
        category_rates: dict[str, dict[str, float]] = {}
        for name, rows in groups.items():
            values = [str(row.get(key, "missing")).strip().lower() for row in rows]
            if not values:
                continue
            counts = Counter(values)
            dominant, count = counts.most_common(1)[0]
            category_summary[name] = f"{dominant} ({count / len(values):.1%})"
            category_rates[name] = {
                value: value_count / len(values) for value, value_count in counts.items()
            }
        if "winner" in category_rates and "deep_failure" in category_rates:
            all_values = set(category_rates["winner"]) | set(category_rates["deep_failure"])
            separation = max(
                abs(
                    category_rates["deep_failure"].get(value, 0.0)
                    - category_rates["winner"].get(value, 0.0)
                )
                for value in all_values
            )
            categorical_rows.append((separation, key, category_summary))

    print("\nTOP NUMERIC SEPARATORS")
    for score, key, summary in sorted(numeric_rows, reverse=True)[:20]:
        print(f"{key:48} separation={score:.3f} values={summary}")

    print("\nTOP CATEGORICAL SEPARATORS")
    for score, key, summary in sorted(categorical_rows, reverse=True)[:20]:
        print(f"{key:48} separation={score:.3f} values={summary}")

    print("\nAVAILABLE PRE-ENTRY KEYS")
    for key in keys:
        print(key)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.paths:
        analyze(path)


if __name__ == "__main__":
    main()
