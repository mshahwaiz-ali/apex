from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

VIABLE_MAX_STOP_R = 1.15
MARGINAL_MAX_STOP_R = 1.30
MIN_NET_TARGET_R = 0.30
MAX_TARGET_COST_DRAG_PCT = 25.0


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
    expected_stop_r: float | None
    projected_net_target_r: float | None
    target_cost_drag_pct: float | None
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
            diagnostics = as_dict(signal.get("diagnostics"))
            geometry = as_dict(diagnostics.get("geometry_audit"))
            realized_r = number(trade.get("realized_r_multiple"))
            decision_time = parse_time(trade.get("decision_time") or signal.get("generated_at"))
            if realized_r is None or decision_time is None:
                continue

            expected_r_value = number(metadata.get("expected_r"))
            expected_stop_r = -expected_r_value if expected_r_value is not None else None
            projected_net_target_r = number(
                geometry.get("net_reward_r")
                or geometry.get("projected_net_r")
                or metadata.get("projected_net_r")
            )
            target_cost_drag_pct = number(
                geometry.get("cost_drag_on_reward_pct") or metadata.get("cost_drag_on_reward_pct")
            )

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
                    expected_stop_r=expected_stop_r,
                    projected_net_target_r=projected_net_target_r,
                    target_cost_drag_pct=target_cost_drag_pct,
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
    if row.expected_stop_r is None:
        return "unknown"
    if row.expected_stop_r <= VIABLE_MAX_STOP_R:
        stop_class = "viable"
    elif row.expected_stop_r <= MARGINAL_MAX_STOP_R:
        stop_class = "marginal"
    else:
        return "reject_stop_cost"

    if row.projected_net_target_r is not None and row.projected_net_target_r < MIN_NET_TARGET_R:
        return "reject_low_net_target"
    if row.target_cost_drag_pct is not None and row.target_cost_drag_pct > MAX_TARGET_COST_DRAG_PCT:
        return "reject_target_cost_drag"
    return stop_class


def metrics(rows: list[Row]) -> tuple[int, int, int, float, float | None]:
    values = [row.realized_r for row in rows]
    wins = [value for value in values if value > 0.0]
    losses = [value for value in values if value < 0.0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    profit_factor = gross_win / gross_loss if gross_loss else (float("inf") if gross_win else None)
    return len(values), len(wins), len(losses), sum(values), profit_factor


def print_metrics(label: str, rows: list[Row]) -> None:
    samples, wins, losses, total_r, profit_factor = metrics(rows)
    print(
        f"  {label:24} samples={samples:3d} wins={wins:3d} losses={losses:3d} "
        f"total_r={total_r:9.4f} pf={profit_factor}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit cost-dominated stop and target geometry in shadow replay episodes."
    )
    parser.add_argument("report_dir", type=Path)
    args = parser.parse_args()

    rows = load_rows(args.report_dir)
    grouped: dict[str, list[Row]] = {}
    for row in rows:
        grouped.setdefault(classify(row), []).append(row)

    accepted = [row for row in rows if classify(row) in {"viable", "marginal"}]
    rejected = [row for row in rows if classify(row).startswith("reject_")]

    print("=" * 78)
    print("APEX 11D.6J — COST-AWARE RISK VIABILITY AUDIT")
    print("=" * 78)
    print_metrics("baseline", rows)
    print_metrics("accepted", accepted)
    print_metrics("rejected", rejected)
    print()
    print("CLASSIFICATION")
    for name in sorted(grouped):
        print_metrics(name, grouped[name])

    removed_winners = sum(row.realized_r > 0.0 for row in rejected)
    removed_losers = sum(row.realized_r < 0.0 for row in rejected)
    print()
    print("FILTER IMPACT")
    print(f"  Removed winners         : {removed_winners}")
    print(f"  Removed losers          : {removed_losers}")
    print(f"  Winner/loss removal     : {removed_winners}/{removed_losers}")
    print()
    print("DECISION")
    accepted_metrics = metrics(accepted)
    accepted_total_r = accepted_metrics[3]
    accepted_pf = accepted_metrics[4]
    if accepted and accepted_total_r > 0.0 and accepted_pf is not None and accepted_pf >= 1.20:
        print("  Cost-aware filtering repairs this sample counterfactually.")
        print("  Keep shadow-only and validate on a larger unseen campaign.")
    else:
        print("  Cost-aware filtering alone does not produce a validated profitable lane.")
        print("  Preserve this as a safety guard, then improve entry generation and lifecycle.")


if __name__ == "__main__":
    main()
