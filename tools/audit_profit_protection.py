from __future__ import annotations

import argparse
import json
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
class Row:
    symbol: str
    timeframe: str
    strategy: str
    direction: str
    decision_time: datetime
    realized_r: float
    mfe_r: float
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
            realized = number(trade.get("realized_r_multiple"))
            mfe = number(
                trade.get("maximum_favorable_excursion_r")
                or metadata.get("maximum_favorable_excursion_r")
            )
            decision_time = parse_time(trade.get("decision_time") or signal.get("generated_at"))
            if realized is None or mfe is None or decision_time is None:
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
                    )
                )
            raw.append(
                Row(
                    symbol=symbol,
                    timeframe=timeframe,
                    strategy=str(signal.get("strategy") or "unknown"),
                    direction=str(signal.get("direction") or "unknown"),
                    decision_time=decision_time,
                    realized_r=realized,
                    mfe_r=mfe,
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


def profit_factor(values: list[float]) -> float | None:
    gross_win = sum(value for value in values if value > 0.0)
    gross_loss = -sum(value for value in values if value < 0.0)
    if gross_loss:
        return gross_win / gross_loss
    return float("inf") if gross_win else None


def simulate(row: Row, trigger_r: float, lock_r: float, partial: float) -> float:
    if row.mfe_r < trigger_r:
        return row.realized_r
    protected_remainder = max(row.realized_r, lock_r)
    return partial * trigger_r + (1.0 - partial) * protected_remainder


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Counterfactual profit-protection audit using observed MFE."
    )
    parser.add_argument("report_dir", type=Path)
    args = parser.parse_args()

    rows = load_rows(args.report_dir)
    baseline = [row.realized_r for row in rows]
    print("=" * 78)
    print("APEX 11D.6I — PROFIT PROTECTION COUNTERFACTUAL")
    print("=" * 78)
    print(f"Unique episodes          : {len(rows)}")
    print(f"Baseline total R         : {sum(baseline):.6f}")
    print(f"Baseline profit factor   : {profit_factor(baseline)}")
    print()

    scenarios: list[tuple[float, float, float]] = []
    for trigger in (0.30, 0.50, 0.75, 1.00):
        for lock in (-0.05, 0.00, 0.10, 0.25):
            for partial in (0.00, 0.25, 0.50):
                if lock > trigger:
                    continue
                scenarios.append((trigger, lock, partial))

    ranked: list[tuple[float, float, float, float, list[float]]] = []
    for trigger, lock, partial in scenarios:
        values = [simulate(row, trigger, lock, partial) for row in rows]
        ranked.append((sum(values), trigger, lock, partial, values))
    ranked.sort(reverse=True, key=lambda item: item[0])

    print("TOP COUNTERFACTUALS")
    for total_r, trigger, lock, partial, values in ranked[:15]:
        wins = sum(value > 0.0 for value in values)
        print(
            f"  trigger={trigger:4.2f}R lock={lock:5.2f}R partial={partial:4.2f} "
            f"total_r={total_r:9.4f} pf={profit_factor(values)} "
            f"wins={wins}/{len(values)}"
        )

    best_total, best_trigger, best_lock, best_partial, _ = ranked[0]
    print()
    print("DECISION")
    if best_total > 0.0:
        print("  Profit protection can make this sample positive counterfactually.")
        print(
            f"  Best candidate: trigger {best_trigger:.2f}R, lock {best_lock:.2f}R, "
            f"partial {best_partial:.2f}."
        )
        print("  Re-simulate chronologically before any production activation.")
    else:
        print("  Profit protection alone cannot repair the negative candidate pool.")
        print("  Entry selection and strategy generation still require redesign.")


if __name__ == "__main__":
    main()
