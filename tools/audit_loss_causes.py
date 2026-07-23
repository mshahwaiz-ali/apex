from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
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


def parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class LossRow:
    symbol: str
    timeframe: str
    strategy: str
    direction: str
    decision_time: datetime
    outcome: str
    net_r: float
    mfe_r: float | None
    mae_r: float | None
    cost_drag_pct: float | None
    stop_distance_pct: float | None
    target_distance_atr: float | None
    higher_timeframe_conflict: bool | None
    immediate_timeframe_conflict: bool | None
    confirmation_complete: bool | None
    entry_filled: bool | None
    same_candle_ambiguous: bool | None
    event_key: str


def bool_or_none(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def load_rows(report_dir: Path) -> list[LossRow]:
    raw: list[LossRow] = []
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
            diagnostics = as_dict(signal.get("diagnostics"))
            confirmation = as_dict(diagnostics.get("confirmation"))
            geometry = as_dict(diagnostics.get("geometry_audit"))
            net_r = number(trade.get("realized_r_multiple"))
            decision_time = parse_time(trade.get("decision_time") or signal.get("generated_at"))
            if net_r is None or net_r >= 0.0 or decision_time is None:
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
                LossRow(
                    symbol=symbol,
                    timeframe=timeframe,
                    strategy=str(signal.get("strategy") or "unknown"),
                    direction=str(signal.get("direction") or "unknown"),
                    decision_time=decision_time,
                    outcome=str(
                        trade.get("outcome") or metadata.get("terminal_state") or "unknown"
                    ),
                    net_r=net_r,
                    mfe_r=number(
                        trade.get("maximum_favorable_excursion_r")
                        or metadata.get("maximum_favorable_excursion_r")
                    ),
                    mae_r=number(
                        trade.get("maximum_adverse_excursion_r")
                        or metadata.get("maximum_adverse_excursion_r")
                    ),
                    cost_drag_pct=number(geometry.get("cost_drag_on_reward_pct")),
                    stop_distance_pct=number(geometry.get("stop_distance_pct")),
                    target_distance_atr=number(geometry.get("tp1_distance_atr")),
                    higher_timeframe_conflict=bool_or_none(
                        confirmation.get("higher_timeframe_conflict")
                    ),
                    immediate_timeframe_conflict=bool_or_none(
                        confirmation.get("immediate_timeframe_conflict")
                    ),
                    confirmation_complete=bool_or_none(
                        confirmation.get("entry_confirmation_complete")
                    ),
                    entry_filled=bool_or_none(metadata.get("entry_filled")),
                    same_candle_ambiguous=bool_or_none(
                        metadata.get("same_candle_ambiguous") or trade.get("same_candle_ambiguous")
                    ),
                    event_key=event_key,
                )
            )

    exact: dict[str, LossRow] = {}
    for row in sorted(raw, key=lambda item: (item.decision_time, item.symbol, item.timeframe)):
        exact.setdefault(row.event_key, row)

    episodes: dict[tuple[str, str, str, int], LossRow] = {}
    for row in exact.values():
        bucket = int(row.decision_time.timestamp()) // (15 * 60)
        episodes.setdefault((row.symbol, row.strategy, row.direction, bucket), row)
    return sorted(episodes.values(), key=lambda item: item.decision_time)


def classify(row: LossRow) -> list[str]:
    causes: list[str] = []
    if row.entry_filled is False:
        causes.append("entry_not_filled")
    if row.higher_timeframe_conflict is True:
        causes.append("higher_timeframe_conflict")
    if row.immediate_timeframe_conflict is True:
        causes.append("immediate_timeframe_conflict")
    if row.confirmation_complete is False:
        causes.append("confirmation_incomplete")
    if row.same_candle_ambiguous is True:
        causes.append("same_candle_ambiguity")
    if row.cost_drag_pct is not None and row.cost_drag_pct >= 30.0:
        causes.append("high_cost_drag")
    if row.stop_distance_pct is not None and row.stop_distance_pct <= 0.30:
        causes.append("stop_too_tight")
    if row.target_distance_atr is not None and row.target_distance_atr >= 2.5:
        causes.append("target_too_far")
    if row.mfe_r is not None and row.mfe_r >= 0.50:
        causes.append("profit_then_reversal")
    if row.mfe_r is not None and row.mfe_r < 0.20 and row.mae_r is not None and row.mae_r <= -0.50:
        causes.append("wrong_direction_or_late_entry")
    if row.outcome == "expired":
        causes.append("expired_without_target")
    if row.outcome == "stop":
        causes.append("stopped_out")
    if not causes:
        causes.append("unclassified")
    return causes


def summarize(rows: list[LossRow]) -> None:
    cause_counts: Counter[str] = Counter()
    by_strategy: dict[str, list[LossRow]] = defaultdict(list)
    by_timeframe: dict[str, list[LossRow]] = defaultdict(list)
    for row in rows:
        cause_counts.update(classify(row))
        by_strategy[row.strategy].append(row)
        by_timeframe[row.timeframe].append(row)

    print("=" * 78)
    print("APEX 11D.6H — LOSS CAUSE AUDIT")
    print("=" * 78)
    print(f"Unique losing episodes   : {len(rows)}")
    print(f"Total losing R           : {sum(row.net_r for row in rows):.6f}")
    print()
    print("DOMINANT LOSS CAUSES")
    for cause, count in cause_counts.most_common():
        print(f"  {cause:32} {count:4d}  ({count / len(rows) * 100.0:6.2f}%)")
    print()
    print("BY STRATEGY")
    for strategy, members in sorted(
        by_strategy.items(), key=lambda item: sum(row.net_r for row in item[1])
    ):
        print(
            f"  {strategy:28} losses={len(members):3d} "
            f"total_r={sum(row.net_r for row in members):9.4f} "
            f"avg_r={sum(row.net_r for row in members) / len(members):8.4f}"
        )
    print()
    print("BY TIMEFRAME")
    for timeframe, members in sorted(
        by_timeframe.items(), key=lambda item: sum(row.net_r for row in item[1])
    ):
        print(
            f"  {timeframe:8} losses={len(members):3d} "
            f"total_r={sum(row.net_r for row in members):9.4f} "
            f"avg_r={sum(row.net_r for row in members) / len(members):8.4f}"
        )
    print()
    dominant = cause_counts.most_common(1)
    print("RECOMMENDATION")
    if dominant:
        print(f"  Fix first: {dominant[0][0]} ({dominant[0][1]} episodes).")
    print("  Keep production behavior unchanged until the revised lane passes unseen data.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit dominant causes of losing shadow episodes.")
    parser.add_argument("report_dir", type=Path)
    args = parser.parse_args()
    rows = load_rows(args.report_dir)
    summarize(rows)


if __name__ == "__main__":
    main()
