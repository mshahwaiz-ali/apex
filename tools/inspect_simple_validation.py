from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MIN_SAMPLE = 5


def as_float(value: object) -> float | None:
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
class Candidate:
    file: str
    symbol: str
    timeframe: str
    decision_time: datetime | None
    strategy: str
    direction: str
    source: str
    actionability: str
    setup_validity: str
    candidate_id: str
    opportunity_id: str
    outcome: str
    net_r: float | None
    expected_r: float | None
    target_touched: bool
    stop_hit: bool
    entry_filled: bool
    selector_outcome: str
    selector_net_r: float | None
    event_id: str


def load_candidates(report_dir: Path) -> tuple[list[Candidate], dict[str, int]]:
    candidates: list[Candidate] = []
    production = Counter()

    for path in sorted(report_dir.glob("*.json")):
        payload = json.loads(path.read_text())
        symbol = str(payload.get("symbol") or "unknown")
        timeframe = str(payload.get("replay_timeframe") or "unknown")
        production["decisions"] += int(payload.get("decision_point_count") or 0)
        production["signals"] += int(payload.get("generated_signal_count") or 0)
        production["no_trade"] += int(payload.get("no_trade_decision_count") or 0)
        production["trades"] += len(payload.get("trades") or [])

        shadow = payload.get("shadow_replay")
        trades = shadow.get("trades") if isinstance(shadow, dict) else None
        if not isinstance(trades, list):
            continue

        for trade in trades:
            if not isinstance(trade, dict):
                continue
            signal = trade.get("signal") if isinstance(trade.get("signal"), dict) else {}
            metadata = trade.get("metadata") if isinstance(trade.get("metadata"), dict) else {}
            selector_outcome = str(metadata.get("recovery_selector_outcome") or "")
            selector_net_r: float | None = None
            if selector_outcome == "select_aggressive":
                selector_net_r = as_float(trade.get("aggressive_reclaim_net_r"))
            elif selector_outcome == "select_retest":
                selector_net_r = as_float(trade.get("retest_recovery_net_r"))

            candidates.append(
                Candidate(
                    file=path.name,
                    symbol=symbol,
                    timeframe=timeframe,
                    decision_time=parse_time(
                        trade.get("decision_time") or signal.get("generated_at")
                    ),
                    strategy=str(signal.get("strategy") or "unknown"),
                    direction=str(signal.get("direction") or "unknown"),
                    source=str(
                        metadata.get("replay_source")
                        or trade.get("replay_reason_code")
                        or "unknown"
                    ),
                    actionability=str(trade.get("actionability_state") or "unknown"),
                    setup_validity=str(metadata.get("setup_validity") or "unknown"),
                    candidate_id=str(
                        metadata.get("candidate_id") or signal.get("candidate_id") or ""
                    ),
                    opportunity_id=str(trade.get("opportunity_id") or ""),
                    outcome=str(
                        trade.get("outcome") or metadata.get("terminal_state") or "unknown"
                    ),
                    net_r=as_float(trade.get("realized_r_multiple") or metadata.get("realized_r")),
                    expected_r=as_float(metadata.get("expected_r")),
                    target_touched=trade.get("target_touched") is True,
                    stop_hit=metadata.get("stop_hit") is True or trade.get("outcome") == "stop",
                    entry_filled=metadata.get("entry_filled") is True,
                    selector_outcome=selector_outcome,
                    selector_net_r=selector_net_r,
                    event_id=str(
                        trade.get("recovery_event_id") or metadata.get("recovery_event_id") or ""
                    ),
                )
            )

    return candidates, dict(production)


def profit_factor(values: Iterable[float]) -> float | None:
    wins = sum(value for value in values if value > 0)
    losses = -sum(value for value in values if value < 0)
    if losses == 0:
        return None if wins == 0 else float("inf")
    return wins / losses


def metrics(rows: list[Candidate], *, selector: bool = False) -> dict[str, Any]:
    values = [
        row.selector_net_r if selector else row.net_r
        for row in rows
        if (row.selector_net_r if selector else row.net_r) is not None
    ]
    numeric = [float(value) for value in values if value is not None]
    wins = sum(value > 0 for value in numeric)
    losses = sum(value < 0 for value in numeric)
    return {
        "samples": len(numeric),
        "wins": wins,
        "losses": losses,
        "win_rate": wins / len(numeric) * 100.0 if numeric else None,
        "total_r": sum(numeric),
        "average_r": sum(numeric) / len(numeric) if numeric else None,
        "profit_factor": profit_factor(numeric),
    }


def representative_key(row: Candidate) -> tuple[Any, ...]:
    return (
        0 if row.entry_filled else 1,
        0 if row.net_r is not None else 1,
        row.decision_time or datetime.max.replace(tzinfo=UTC),
        row.file,
        row.candidate_id,
    )


def dedupe_exact(rows: list[Candidate]) -> list[Candidate]:
    grouped: dict[tuple[str, str, str, str, str], list[Candidate]] = defaultdict(list)
    for row in rows:
        key = (
            row.symbol,
            row.timeframe,
            row.strategy,
            row.direction,
            row.opportunity_id or row.candidate_id or str(row.decision_time),
        )
        grouped[key].append(row)
    return [sorted(group, key=representative_key)[0] for group in grouped.values()]


def episode_key(row: Candidate) -> tuple[str, str, str, int]:
    timestamp = int((row.decision_time or datetime.min.replace(tzinfo=UTC)).timestamp())
    return (row.symbol, row.strategy, row.direction, timestamp // (15 * 60))


def dedupe_cross_timeframe(rows: list[Candidate]) -> list[Candidate]:
    grouped: dict[tuple[str, str, str, int], list[Candidate]] = defaultdict(list)
    for row in rows:
        grouped[episode_key(row)].append(row)
    return [sorted(group, key=representative_key)[0] for group in grouped.values()]


def print_metrics(label: str, result: dict[str, Any]) -> None:
    print(label)
    for key in ("samples", "wins", "losses", "win_rate", "total_r", "average_r", "profit_factor"):
        print(f"  {key:14}: {result[key]}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect simple-validation backtests without changing production behavior."
    )
    parser.add_argument("report_dir", type=Path)
    args = parser.parse_args()

    candidates, production = load_candidates(args.report_dir)
    exact = dedupe_exact(candidates)
    episodes = dedupe_cross_timeframe(exact)

    print("=" * 78)
    print("APEX SIMPLE VALIDATION INSPECTION")
    print("=" * 78)
    print(f"Report directory         : {args.report_dir}")
    print(f"JSON reports             : {len(list(args.report_dir.glob('*.json')))}")
    print(f"Production decisions     : {production.get('decisions', 0)}")
    print(f"Production signals       : {production.get('signals', 0)}")
    print(f"Production trades        : {production.get('trades', 0)}")
    print(f"Production no-trade      : {production.get('no_trade', 0)}")
    print()

    print(f"Raw shadow rows          : {len(candidates)}")
    print(f"Exact unique rows        : {len(exact)}")
    print(f"Cross-TF episodes        : {len(episodes)}")
    print_metrics("SHADOW — EXACT UNIQUE", metrics(exact))
    print()
    print_metrics("SHADOW — CROSS-TF EPISODES", metrics(episodes))
    print()

    selector_rows_by_event: dict[str, Candidate] = {}
    for row in candidates:
        if row.selector_outcome not in {"select_aggressive", "select_retest"}:
            continue
        key = row.event_id or "|".join(
            [row.symbol, row.timeframe, row.strategy, row.direction, str(row.decision_time)]
        )
        selector_rows_by_event.setdefault(key, row)
    selector_rows = list(selector_rows_by_event.values())
    print_metrics("CURRENT RECOVERY SELECTOR", metrics(selector_rows, selector=True))
    print()

    dimensions = {
        "timeframe": lambda row: row.timeframe,
        "strategy": lambda row: row.strategy,
        "source": lambda row: row.source,
        "actionability": lambda row: row.actionability,
        "setup_validity": lambda row: row.setup_validity,
    }

    print("DIAGNOSTIC PROFITABLE LANES — NOT PRODUCTION APPROVAL")
    profitable: list[tuple[float, str, str, dict[str, Any]]] = []
    for dimension, getter in dimensions.items():
        groups: dict[str, list[Candidate]] = defaultdict(list)
        for row in episodes:
            groups[getter(row)].append(row)
        for name, members in groups.items():
            result = metrics(members)
            if result["samples"] < MIN_SAMPLE or result["total_r"] <= 0:
                continue
            pf = result["profit_factor"]
            score = float("inf") if pf == float("inf") else float(pf or 0.0)
            profitable.append((score, dimension, name, result))

    for _, dimension, name, result in sorted(profitable, reverse=True):
        print(f"  {dimension}={name}: {result}")
    if not profitable:
        print(f"  None with minimum sample {MIN_SAMPLE} and positive total R.")

    print()
    print("RECOMMENDATION")
    if production.get("trades", 0) == 0:
        print("  Production remains over-restrictive in this sample.")
    selector_result = metrics(selector_rows, selector=True)
    if selector_result["samples"] and selector_result["total_r"] <= 0:
        print("  Do not activate the current recovery selector; selected sample is net negative.")
    if not profitable:
        print("  Do not loosen all gates. Expand the sample and validate a focused lane first.")
    else:
        print("  Re-test only the strongest positive lane on an unseen period before activation.")


if __name__ == "__main__":
    main()
