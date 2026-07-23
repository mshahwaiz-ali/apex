from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def as_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def boolean(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


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


@dataclass(frozen=True)
class Row:
    symbol: str
    timeframe: str
    strategy: str
    direction: str
    decision_time: datetime
    realized_r: float
    mfe_r: float | None
    thesis_outcome: str
    direction_correct_at_horizon: bool | None
    target_before_invalidation: bool | None
    invalidation_before_target: bool | None
    late_reentry_available: bool | None
    post_stop_classification: str
    post_stop_entry_reclaimed: bool | None
    post_stop_tp1_reached: bool | None
    deep_directional_failure: bool | None
    activation_required: bool | None
    activation_outcome: str
    event_key: str


def load_rows(report_dir: Path) -> list[Row]:
    raw: list[Row] = []
    for path in sorted(report_dir.glob("*.json")):
        payload = as_dict(json.loads(path.read_text()))
        symbol = str(payload.get("symbol") or "unknown")
        timeframe = str(payload.get("replay_timeframe") or "unknown")
        shadow = as_dict(payload.get("shadow_replay"))
        trades = shadow.get("trades")
        if not isinstance(trades, list):
            continue

        for trade_value in trades:
            trade = as_dict(trade_value)
            signal = as_dict(trade.get("signal"))
            metadata = as_dict(trade.get("metadata"))
            realized_r = number(trade.get("realized_r_multiple"))
            decision_time = parse_time(trade.get("decision_time") or signal.get("generated_at"))
            if realized_r is None or decision_time is None:
                continue

            event_key = str(trade.get("recovery_event_id") or trade.get("opportunity_id") or "")
            if not event_key:
                event_key = "|".join(
                    (
                        symbol,
                        timeframe,
                        str(signal.get("strategy") or "unknown"),
                        str(signal.get("direction") or "unknown"),
                        decision_time.isoformat(),
                        str(metadata.get("candidate_id") or signal.get("candidate_id") or ""),
                    )
                )

            raw.append(
                Row(
                    symbol=symbol,
                    timeframe=timeframe,
                    strategy=str(signal.get("strategy") or "unknown"),
                    direction=str(signal.get("direction") or "unknown"),
                    decision_time=decision_time,
                    realized_r=realized_r,
                    mfe_r=number(
                        trade.get("maximum_favorable_excursion_r")
                        or metadata.get("maximum_favorable_excursion_r")
                    ),
                    thesis_outcome=str(metadata.get("thesis_outcome") or "unknown"),
                    direction_correct_at_horizon=boolean(
                        metadata.get("direction_correct_at_horizon")
                    ),
                    target_before_invalidation=boolean(
                        metadata.get("target_before_invalidation")
                    ),
                    invalidation_before_target=boolean(
                        metadata.get("invalidation_before_target")
                    ),
                    late_reentry_available=boolean(metadata.get("late_reentry_available")),
                    post_stop_classification=str(
                        metadata.get("post_stop_classification") or "unknown"
                    ),
                    post_stop_entry_reclaimed=boolean(
                        metadata.get("post_stop_entry_reclaimed")
                    ),
                    post_stop_tp1_reached=boolean(metadata.get("post_stop_tp1_reached")),
                    deep_directional_failure=boolean(metadata.get("deep_directional_failure")),
                    activation_required=boolean(metadata.get("activation_required")),
                    activation_outcome=str(metadata.get("activation_outcome") or "unknown"),
                    event_key=event_key,
                )
            )

    exact: dict[str, Row] = {}
    for row in sorted(raw, key=lambda item: (item.decision_time, item.symbol, item.timeframe)):
        exact.setdefault(row.event_key, row)

    episodes: dict[tuple[str, str, str, int], Row] = {}
    for row in exact.values():
        bucket = int(row.decision_time.timestamp()) // (15 * 60)
        episodes.setdefault((row.symbol, row.strategy, row.direction, bucket), row)
    return sorted(episodes.values(), key=lambda item: item.decision_time)


def classify(row: Row) -> str:
    if row.realized_r >= 0.0:
        return "profitable_or_flat"
    if row.deep_directional_failure is True or row.thesis_outcome == "thesis_wrong":
        return "wrong_direction"
    if row.invalidation_before_target is True:
        return "wrong_direction_or_structure_failure"
    if row.late_reentry_available is True and (
        row.post_stop_entry_reclaimed is True or row.post_stop_tp1_reached is True
    ):
        return "entered_too_early"
    if row.thesis_outcome in {"thesis_correct", "thesis_partially_correct"}:
        return "correct_direction_bad_execution"
    if row.mfe_r is not None and row.mfe_r >= 0.50:
        return "profit_available_not_captured"
    if row.activation_required is False and row.mfe_r is not None and row.mfe_r < 0.20:
        return "direct_cmp_fill_failed"
    if row.activation_required is True and row.activation_outcome == "triggered":
        return "conditional_entry_failed_after_trigger"
    if row.direction_correct_at_horizon is False:
        return "wrong_direction_at_horizon"
    return "unresolved"


def summarize(rows: list[Row]) -> None:
    losses = [row for row in rows if row.realized_r < 0.0]
    counts = Counter(classify(row) for row in losses)
    by_strategy: dict[str, Counter[str]] = defaultdict(Counter)
    by_timeframe: dict[str, Counter[str]] = defaultdict(Counter)
    for row in losses:
        category = classify(row)
        by_strategy[row.strategy][category] += 1
        by_timeframe[row.timeframe][category] += 1

    print("=" * 78)
    print("APEX 11D.6K — DIRECTION AND ENTRY-TIMING FAILURE AUDIT")
    print("=" * 78)
    print(f"Unique episodes          : {len(rows)}")
    print(f"Losing episodes          : {len(losses)}")
    print(f"Total losing R           : {sum(row.realized_r for row in losses):.6f}")
    print()
    print("PRIMARY FAILURE CLASSES")
    for category, count in counts.most_common():
        print(f"  {category:38} {count:4d}  ({count / len(losses) * 100.0:6.2f}%)")

    print()
    print("BY STRATEGY")
    for strategy, categories in sorted(by_strategy.items()):
        dominant, count = categories.most_common(1)[0]
        total = sum(categories.values())
        print(f"  {strategy:28} losses={total:3d} dominant={dominant} ({count})")

    print()
    print("BY TIMEFRAME")
    for timeframe, categories in sorted(by_timeframe.items()):
        dominant, count = categories.most_common(1)[0]
        total = sum(categories.values())
        print(f"  {timeframe:8} losses={total:3d} dominant={dominant} ({count})")

    wrong_direction = counts["wrong_direction"] + counts["wrong_direction_or_structure_failure"]
    execution_failures = (
        counts["entered_too_early"]
        + counts["correct_direction_bad_execution"]
        + counts["profit_available_not_captured"]
        + counts["direct_cmp_fill_failed"]
        + counts["conditional_entry_failed_after_trigger"]
    )

    print()
    print("DECISION")
    if wrong_direction > execution_failures:
        print("  Direction and regime routing are the dominant defects.")
        print("  Fix strategy routing and higher-timeframe directional authority first.")
    elif execution_failures > wrong_direction:
        print("  Entry timing and activation are the dominant defects.")
        print("  Fix direct CMP fills, retest timing, and confirmation sequencing first.")
    else:
        print("  Direction and execution defects are similarly material.")
        print("  Apply separate routing and entry-timing fixes, then re-run unseen validation.")
    print("  Do not loosen production gates from this sample alone.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify whether losing shadow trades failed from direction or entry timing."
    )
    parser.add_argument("report_dir", type=Path)
    args = parser.parse_args()
    summarize(load_rows(args.report_dir))


if __name__ == "__main__":
    main()
