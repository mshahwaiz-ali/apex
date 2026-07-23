from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

POINTER = Path("/tmp/apex_11d6d_part2e_latest_run_dir")
MIN_NET_R = 0.30


def value(trade: dict[str, Any], key: str, default: Any = None) -> Any:
    if key in trade:
        return trade[key]
    metadata = trade.get("metadata")
    if isinstance(metadata, dict):
        return metadata.get(key, default)
    return default


def number(item: object) -> float | None:
    if isinstance(item, bool):
        return None
    if isinstance(item, (int, float)):
        return float(item)
    return None


def trades_from(payload: dict[str, Any]) -> list[dict[str, Any]]:
    shadow = payload.get("shadow_replay")
    if isinstance(shadow, dict) and isinstance(shadow.get("trades"), list):
        return [row for row in shadow["trades"] if isinstance(row, dict)]

    report = payload.get("report")
    if isinstance(report, dict) and isinstance(report.get("trades"), list):
        return [row for row in report["trades"] if isinstance(row, dict)]

    trades = payload.get("trades")
    if isinstance(trades, list):
        return [row for row in trades if isinstance(row, dict)]

    return []


def signal_value(trade: dict[str, Any], key: str, default: str = "") -> str:
    signal = trade.get("signal")
    if isinstance(signal, dict):
        item = signal.get(key)
        if item is not None:
            return str(item)
    item = value(trade, key, default)
    return str(item or default)


def representative_key(row: dict[str, Any]) -> tuple[Any, ...]:
    selected = 0 if row["event_selected"] else 1
    rank = row["event_rank"]
    rank_value = rank if isinstance(rank, int) else 999999
    return (
        selected,
        rank_value,
        row["generated_at"],
        row["candidate_id"],
        row["file"],
    )


def unique_rows(
    rows: list[dict[str, Any]],
    *,
    id_key: str,
    available_key: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        if row[available_key] is not True:
            continue
        event_id = str(row.get(id_key) or "")
        if event_id:
            grouped[event_id].append(row)

    return [sorted(members, key=representative_key)[0] for members in grouped.values()]


def mode_summary(
    rows: list[dict[str, Any]],
    prefix: str,
) -> dict[str, Any]:
    available = [row for row in rows if row[f"{prefix}_available"]]
    outcomes = Counter(row[f"{prefix}_outcome"] for row in available)

    net_values = [row[f"{prefix}_net_r"] for row in available if row[f"{prefix}_net_r"] is not None]

    speed: dict[str, list[dict[str, Any]]] = {
        "fast": [],
        "normal": [],
        "slow": [],
    }

    for row in available:
        bars = row[f"{prefix}_bars"]
        if bars is None:
            continue
        if bars <= 3:
            speed["fast"].append(row)
        elif bars <= 8:
            speed["normal"].append(row)
        else:
            speed["slow"].append(row)

    speed_summary: dict[str, dict[str, Any]] = {}
    for name, members in speed.items():
        member_net = [
            row[f"{prefix}_net_r"] for row in members if row[f"{prefix}_net_r"] is not None
        ]
        member_outcomes = Counter(row[f"{prefix}_outcome"] for row in members)
        speed_summary[name] = {
            "events": len(members),
            "targets": member_outcomes["target"],
            "stops": member_outcomes["stop"],
            "expired": member_outcomes["expired"],
            "average_net_r": (sum(member_net) / len(member_net) if member_net else None),
            "total_net_r": sum(member_net),
            "gate_passes": sum(result >= MIN_NET_R for result in member_net),
            "ambiguities": sum(row[f"{prefix}_ambiguous"] for row in members),
        }

    count = len(available)

    return {
        "events": count,
        "targets": outcomes["target"],
        "stops": outcomes["stop"],
        "expired": outcomes["expired"],
        "target_rate": (outcomes["target"] / count * 100.0 if count else None),
        "positive_net": sum(
            row[f"{prefix}_net_r"] is not None and row[f"{prefix}_net_r"] > 0.0 for row in available
        ),
        "gate_passes": sum(
            row[f"{prefix}_net_r"] is not None and row[f"{prefix}_net_r"] >= MIN_NET_R
            for row in available
        ),
        "ambiguities": sum(row[f"{prefix}_ambiguous"] for row in available),
        "average_net_r": (sum(net_values) / len(net_values) if net_values else None),
        "total_net_r": sum(net_values),
        "speed": speed_summary,
    }


if not POINTER.exists():
    raise SystemExit(
        "Latest campaign pointer missing. Run tools/run_11d6d_part2e_campaign.py first."
    )

run_dir = Path(POINTER.read_text().strip())

files = sorted(
    path
    for path in run_dir.glob("*.json")
    if path.name != "campaign_summary.json" and "inspection" not in path.name
)

rows: list[dict[str, Any]] = []
errors: list[str] = []

for path in files:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        errors.append(f"{path.name}: {exc}")
        continue

    symbol = str(payload.get("symbol") or "unknown")
    timeframe = str(payload.get("replay_timeframe") or payload.get("timeframe") or "unknown")

    for trade in trades_from(payload):
        aggressive_available = value(trade, "aggressive_reclaim_entry_available") is True
        retest_available = value(trade, "retest_recovery_entry_available") is True

        if not aggressive_available and not retest_available:
            continue

        pair_class = value(
            trade,
            "recovery_entry_pair_classification",
        )
        if not isinstance(pair_class, str):
            if aggressive_available and retest_available:
                pair_class = "both_available"
            elif aggressive_available:
                pair_class = "aggressive_only"
            elif retest_available:
                pair_class = "retest_only"
            else:
                pair_class = "neither_available"

        aggressive_net = number(value(trade, "aggressive_reclaim_net_r"))
        retest_net = number(value(trade, "retest_recovery_net_r"))

        event_rank = value(trade, "recovery_event_rank")
        event_rank = event_rank if isinstance(event_rank, int) else None

        rows.append(
            {
                "file": path.name,
                "symbol": symbol,
                "timeframe": timeframe,
                "strategy": signal_value(trade, "strategy", "unknown"),
                "direction": signal_value(trade, "direction", "unknown"),
                "candidate_id": signal_value(trade, "candidate_id"),
                "generated_at": signal_value(trade, "generated_at"),
                "reclaim_time": str(value(trade, "recovery_reclaim_time", "")),
                "event_id_strict": str(value(trade, "recovery_event_id_strict", "")),
                "event_id_current": str(value(trade, "recovery_event_id", "")),
                "event_id_loose": str(value(trade, "recovery_event_id_loose", "")),
                "market_episode_id": str(value(trade, "recovery_market_episode_id", "")),
                "event_selected": (value(trade, "recovery_event_selected") is True),
                "event_rank": event_rank,
                "event_members": value(
                    trade,
                    "recovery_event_member_count",
                    0,
                ),
                "pair_class": pair_class,
                "aggressive_available": aggressive_available,
                "aggressive_outcome": str(
                    value(
                        trade,
                        "aggressive_reclaim_outcome",
                        "unavailable",
                    )
                ),
                "aggressive_net_r": aggressive_net,
                "aggressive_bars": number(
                    value(
                        trade,
                        "aggressive_reclaim_bars_to_outcome",
                    )
                ),
                "aggressive_ambiguous": (
                    value(
                        trade,
                        "aggressive_reclaim_same_candle_ambiguous",
                    )
                    is True
                ),
                "retest_available": retest_available,
                "retest_outcome": str(
                    value(
                        trade,
                        "retest_recovery_outcome",
                        "unavailable",
                    )
                ),
                "retest_net_r": retest_net,
                "retest_bars": number(
                    value(
                        trade,
                        "retest_recovery_bars_to_outcome",
                    )
                ),
                "retest_ambiguous": (
                    value(
                        trade,
                        "retest_recovery_same_candle_ambiguous",
                    )
                    is True
                ),
            }
        )

strict = unique_rows(
    rows,
    id_key="event_id_strict",
    available_key="aggressive_available",
)
current = unique_rows(
    rows,
    id_key="event_id_current",
    available_key="aggressive_available",
)
loose = unique_rows(
    rows,
    id_key="event_id_loose",
    available_key="aggressive_available",
)
retest = unique_rows(
    rows,
    id_key="event_id_current",
    available_key="retest_available",
)

aggressive_summary = mode_summary(current, "aggressive")
retest_summary = mode_summary(retest, "retest")

paired_events: dict[str, dict[str, Any]] = {}

for row in current + retest:
    event_id = row["event_id_current"]
    if not event_id:
        continue
    previous = paired_events.get(event_id)
    if previous is None or representative_key(row) < representative_key(previous):
        paired_events[event_id] = row

paired_rows = list(paired_events.values())
pair_counts = Counter(row["pair_class"] for row in paired_rows)

paired_deltas: list[float] = []
aggressive_better = 0
retest_better = 0
ties = 0

for row in paired_rows:
    if not row["aggressive_available"] or not row["retest_available"]:
        continue

    aggressive_net = row["aggressive_net_r"]
    retest_net = row["retest_net_r"]

    if aggressive_net is None or retest_net is None:
        continue

    delta = aggressive_net - retest_net
    paired_deltas.append(delta)

    if delta > 0:
        aggressive_better += 1
    elif delta < 0:
        retest_better += 1
    else:
        ties += 1

episode_ids = {row["market_episode_id"] for row in paired_rows if row["market_episode_id"]}

raw_aggressive = sum(row["aggressive_available"] for row in rows)
raw_retest = sum(row["retest_available"] for row in rows)

print()
print("=" * 78)
print("APEX 11D.6D PART 2E — ROBUSTNESS INSPECTION")
print("=" * 78)
print(f"Campaign directory       : {run_dir}")
print(f"JSON reports             : {len(files)}")
print(f"Invalid reports          : {len(errors)}")
print()

print("EVENT IDENTITY")
print(f"  Raw aggressive entries : {raw_aggressive}")
print(f"  Strict unique events   : {len(strict)}")
print(f"  Current unique events  : {len(current)}")
print(f"  Loose unique events    : {len(loose)}")
print(f"  Current duplicates     : {raw_aggressive - len(current)}")
print(f"  Market episodes        : {len(episode_ids)}")
print(f"  Strict-current delta   : {len(strict) - len(current)}")
print(f"  Current-loose delta    : {len(current) - len(loose)}")
print()

print("AGGRESSIVE RECLAIM")
for key, item in aggressive_summary.items():
    if key != "speed":
        print(f"  {key:22}: {item}")

print()
print("AGGRESSIVE SPEED PERFORMANCE")
for name, item in aggressive_summary["speed"].items():
    print(f"  {name:7}: {item}")

print()
print("RETEST RECOVERY")
print(f"  Raw retest entries     : {raw_retest}")
for key, item in retest_summary.items():
    if key != "speed":
        print(f"  {key:22}: {item}")

print()
print("RETEST SPEED PERFORMANCE")
for name, item in retest_summary["speed"].items():
    print(f"  {name:7}: {item}")

print()
print("PAIRED AGGRESSIVE VS RETEST")
print(f"  Pair classifications   : {dict(pair_counts)}")
print(f"  Comparable paired rows : {len(paired_deltas)}")
print(f"  Aggressive better      : {aggressive_better}")
print(f"  Retest better          : {retest_better}")
print(f"  Ties                   : {ties}")
print(
    "  Avg aggressive-retest : "
    f"{sum(paired_deltas) / len(paired_deltas) if paired_deltas else None}"
)
print(f"  Total difference       : {sum(paired_deltas)}")

print()
print("BY TIMEFRAME — AGGRESSIVE")
by_timeframe: dict[str, list[dict[str, Any]]] = defaultdict(list)
for row in current:
    by_timeframe[row["timeframe"]].append(row)

for timeframe, members in sorted(by_timeframe.items()):
    print(f"  {timeframe}: {mode_summary(members, 'aggressive')}")

print()
print("BY SYMBOL — AGGRESSIVE")
by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
for row in current:
    by_symbol[row["symbol"]].append(row)

for symbol, members in sorted(by_symbol.items()):
    print(f"  {symbol}: {mode_summary(members, 'aggressive')}")

print()
print("BY STRATEGY — AGGRESSIVE")
by_strategy: dict[str, list[dict[str, Any]]] = defaultdict(list)
for row in current:
    by_strategy[row["strategy"]].append(row)

for strategy, members in sorted(by_strategy.items()):
    print(f"  {strategy}: {mode_summary(members, 'aggressive')}")

print()
print("BY DIRECTION — AGGRESSIVE")
by_direction: dict[str, list[dict[str, Any]]] = defaultdict(list)
for row in current:
    by_direction[row["direction"]].append(row)

for direction, members in sorted(by_direction.items()):
    print(f"  {direction}: {mode_summary(members, 'aggressive')}")

print()
print("SELECTED AGGRESSIVE EVENTS")
for row in sorted(
    current,
    key=lambda item: (
        item["symbol"],
        item["timeframe"],
        item["reclaim_time"],
    ),
):
    print(
        f"  {row['symbol']} {row['timeframe']} "
        f"{row['strategy']} {row['direction']} | "
        f"{row['aggressive_outcome']} | "
        f"net={row['aggressive_net_r']}R | "
        f"bars={row['aggressive_bars']} | "
        f"members={row['event_members']} | "
        f"pair={row['pair_class']} | "
        f"ambiguous={row['aggressive_ambiguous']}"
    )

if errors:
    print()
    print("ERRORS")
    for error in errors:
        print(f"  {error}")

print("=" * 78)


def _print_selector_diagnostics() -> None:
    outcome_counts: Counter[str] = Counter()
    realized_counts: Counter[str] = Counter()
    raw_rows = 0
    unique_events = 0
    duplicates = 0
    evaluable = 0
    correct = 0
    failure_to_abstain = 0
    less_bad = 0

    for report_path in files:
        payload = json.loads(report_path.read_text())
        shadow = payload.get("shadow_replay")
        if not isinstance(shadow, dict):
            continue
        sweep = shadow.get("sweep_reclaim_metrics")
        if not isinstance(sweep, dict):
            continue
        paired = sweep.get("paired_entry_comparison")
        if not isinstance(paired, dict):
            continue

        outcomes = paired.get("selector_outcome_counts")
        if isinstance(outcomes, dict):
            outcome_counts.update(
                {str(key): int(count) for key, count in outcomes.items() if isinstance(count, int)}
            )
        realized = paired.get("selector_realized_classification_counts")
        if isinstance(realized, dict):
            realized_counts.update(
                {str(key): int(count) for key, count in realized.items() if isinstance(count, int)}
            )
        raw_rows += int(paired.get("selector_raw_row_count") or 0)
        unique_events += int(paired.get("selector_unique_event_count") or 0)
        duplicates += int(paired.get("selector_duplicate_row_count") or 0)
        evaluable += int(paired.get("selector_evaluable_count") or 0)
        correct += int(paired.get("selector_correct_count") or 0)
        failure_to_abstain += int(paired.get("selector_failure_to_abstain_count") or 0)
        less_bad += int(paired.get("selector_less_bad_selection_count") or 0)

    print()
    print("RECOVERY SELECTOR")
    print(f"  Outcomes              : {dict(outcome_counts)}")
    print(f"  Realized classes      : {dict(realized_counts)}")
    print(f"  Raw selector rows     : {raw_rows}")
    print(f"  Unique selector events: {unique_events}")
    print(f"  Duplicate rows        : {duplicates}")
    print(f"  Evaluable decisions   : {evaluable}")
    print(f"  Correct decisions     : {correct}")
    print(f"  Selector accuracy     : {correct / evaluable if evaluable else None}")
    print(f"  Failed to abstain     : {failure_to_abstain}")
    print(f"  Less-bad selections   : {less_bad}")
    print("  Diagnostic only       : True")
    print("  Production changed    : False")


def _print_selector_event_details() -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for report_path in files:
        payload = json.loads(report_path.read_text())
        symbol = str(payload.get("symbol") or "unknown")
        timeframe = str(payload.get("replay_timeframe") or payload.get("timeframe") or "unknown")

        for trade in trades_from(payload):
            if value(trade, "recovery_pair_available") is not True:
                continue

            event_id = str(value(trade, "recovery_event_id") or "")
            if not event_id:
                continue

            rank = value(trade, "recovery_event_rank")
            selected = value(trade, "recovery_event_selected") is True
            generated_at = str(
                value(trade, "generated_at") or value(trade, "signal_generated_at") or ""
            )
            candidate_id = str(value(trade, "candidate_id") or value(trade, "signal_id") or "")

            grouped[event_id].append(
                {
                    "file": report_path.name,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "strategy": signal_value(trade, "strategy", "unknown"),
                    "direction": signal_value(trade, "direction", "unknown"),
                    "selected": selected,
                    "rank": rank if isinstance(rank, int) else None,
                    "generated_at": generated_at,
                    "candidate_id": candidate_id,
                    "selector_outcome": str(value(trade, "recovery_selector_outcome") or "unknown"),
                    "selector_reason": str(value(trade, "recovery_selector_reason") or "unknown"),
                    "aggressive_viability": str(
                        value(
                            trade,
                            "recovery_selector_aggressive_viability",
                        )
                        or "unknown"
                    ),
                    "retest_viability": str(
                        value(
                            trade,
                            "recovery_selector_retest_viability",
                        )
                        or "unknown"
                    ),
                    "aggressive_projected_net_r": number(
                        value(
                            trade,
                            "recovery_pair_aggressive_projected_net_r",
                        )
                    ),
                    "retest_projected_net_r": number(
                        value(
                            trade,
                            "recovery_pair_retest_projected_net_r",
                        )
                    ),
                    "aggressive_preference_score": number(
                        value(
                            trade,
                            "recovery_pair_aggressive_preference_score",
                        )
                    ),
                    "retest_preference_score": number(
                        value(
                            trade,
                            "recovery_pair_retest_preference_score",
                        )
                    ),
                    "aggressive_realized_net_r": number(value(trade, "aggressive_reclaim_net_r")),
                    "retest_realized_net_r": number(value(trade, "retest_recovery_net_r")),
                    "realized_classification": str(
                        value(
                            trade,
                            "recovery_selector_realized_classification",
                        )
                        or "unknown"
                    ),
                    "correct": value(trade, "recovery_selector_correct") is True,
                }
            )

    def representative_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        rank = row["rank"]
        return (
            0 if row["selected"] else 1,
            rank if isinstance(rank, int) else 999999,
            row["generated_at"],
            row["candidate_id"],
            row["file"],
        )

    representatives = [
        sorted(members, key=representative_sort_key)[0] for members in grouped.values()
    ]
    representatives.sort(
        key=lambda row: (
            row["symbol"],
            row["timeframe"],
            row["strategy"],
            row["direction"],
        )
    )

    print()
    print("SELECTOR EVENT DETAILS")
    if not representatives:
        print("  No paired selector events found.")
        return

    for row in representatives:
        print(f"  {row['symbol']} {row['timeframe']} {row['strategy']} {row['direction']}")
        print(f"    Decision     : {row['selector_outcome']} | correct={row['correct']}")
        print(f"    Reason       : {row['selector_reason']}")
        print(
            "    Viability    : "
            f"aggressive={row['aggressive_viability']} "
            f"| retest={row['retest_viability']}"
        )
        print(
            "    Projected R  : "
            f"aggressive={row['aggressive_projected_net_r']} "
            f"| retest={row['retest_projected_net_r']}"
        )
        print(
            "    Pref score   : "
            f"aggressive={row['aggressive_preference_score']} "
            f"| retest={row['retest_preference_score']}"
        )
        print(
            "    Realized R   : "
            f"aggressive={row['aggressive_realized_net_r']} "
            f"| retest={row['retest_realized_net_r']}"
        )
        print(f"    Realized class: {row['realized_classification']}")


_print_selector_event_details()


def _print_projection_calibration() -> None:
    aggressive_errors: list[float] = []
    retest_errors: list[float] = []
    aggressive_absolute_errors: list[float] = []
    retest_absolute_errors: list[float] = []
    aggressive_over = 0
    aggressive_under = 0
    retest_over = 0
    retest_under = 0
    by_timeframe: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"aggressive": [], "retest": []}
    )
    by_strategy: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"aggressive": [], "retest": []}
    )

    seen_events: set[str] = set()

    for report_path in files:
        payload = json.loads(report_path.read_text())
        timeframe = str(payload.get("replay_timeframe") or payload.get("timeframe") or "unknown")

        for trade in trades_from(payload):
            if value(trade, "recovery_pair_available") is not True:
                continue

            event_id = str(value(trade, "recovery_event_id") or "")
            if not event_id or event_id in seen_events:
                continue
            seen_events.add(event_id)

            strategy = signal_value(trade, "strategy", "unknown")
            aggressive_projected = number(value(trade, "recovery_pair_aggressive_projected_net_r"))
            aggressive_realized = number(value(trade, "aggressive_reclaim_net_r"))
            retest_projected = number(value(trade, "recovery_pair_retest_projected_net_r"))
            retest_realized = number(value(trade, "retest_recovery_net_r"))

            if aggressive_projected is not None and aggressive_realized is not None:
                error = aggressive_projected - aggressive_realized
                aggressive_errors.append(error)
                aggressive_absolute_errors.append(abs(error))
                aggressive_over += int(error > 0.0)
                aggressive_under += int(error < 0.0)
                by_timeframe[timeframe]["aggressive"].append(error)
                by_strategy[strategy]["aggressive"].append(error)

            if retest_projected is not None and retest_realized is not None:
                error = retest_projected - retest_realized
                retest_errors.append(error)
                retest_absolute_errors.append(abs(error))
                retest_over += int(error > 0.0)
                retest_under += int(error < 0.0)
                by_timeframe[timeframe]["retest"].append(error)
                by_strategy[strategy]["retest"].append(error)

    def avg(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    print()
    print("PROJECTION CALIBRATION")
    print(
        "  Aggressive count/avg error/MAE : "
        f"{len(aggressive_errors)} / {avg(aggressive_errors)} / "
        f"{avg(aggressive_absolute_errors)}"
    )
    print(f"  Aggressive over/under          : {aggressive_over} / {aggressive_under}")
    print(
        "  Retest count/avg error/MAE     : "
        f"{len(retest_errors)} / {avg(retest_errors)} / "
        f"{avg(retest_absolute_errors)}"
    )
    print(f"  Retest over/under              : {retest_over} / {retest_under}")

    print("  By timeframe:")
    for timeframe, modes in sorted(by_timeframe.items()):
        print(
            f"    {timeframe}: "
            f"aggressive_avg_error={avg(modes['aggressive'])} "
            f"| retest_avg_error={avg(modes['retest'])}"
        )

    print("  By strategy:")
    for strategy, modes in sorted(by_strategy.items()):
        print(
            f"    {strategy}: "
            f"aggressive_avg_error={avg(modes['aggressive'])} "
            f"| retest_avg_error={avg(modes['retest'])}"
        )

    print("  Diagnostic only                : True")
    print("  Production changed             : False")


_print_projection_calibration()


def _print_attainability_diagnostics() -> None:
    rows: list[dict[str, Any]] = []
    seen_events: set[str] = set()

    for report_path in files:
        payload = json.loads(report_path.read_text())
        symbol = str(payload.get("symbol") or "unknown")
        timeframe = str(payload.get("replay_timeframe") or payload.get("timeframe") or "unknown")

        for trade in trades_from(payload):
            if value(trade, "recovery_pair_available") is not True:
                continue

            event_id = str(value(trade, "recovery_event_id") or "")
            if not event_id or event_id in seen_events:
                continue
            seen_events.add(event_id)

            rows.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "strategy": signal_value(trade, "strategy", "unknown"),
                    "direction": signal_value(trade, "direction", "unknown"),
                    "aggressive_structural": number(
                        value(trade, "recovery_pair_aggressive_projected_net_r")
                    ),
                    "aggressive_factor": number(
                        value(trade, "recovery_pair_aggressive_attainability_factor")
                    ),
                    "aggressive_attainable": number(
                        value(
                            trade,
                            "recovery_pair_aggressive_attainable_projected_net_r",
                        )
                    ),
                    "aggressive_viability": str(
                        value(
                            trade,
                            "recovery_pair_aggressive_attainability_viability",
                        )
                        or "unknown"
                    ),
                    "retest_structural": number(
                        value(trade, "recovery_pair_retest_projected_net_r")
                    ),
                    "retest_factor": number(
                        value(trade, "recovery_pair_retest_attainability_factor")
                    ),
                    "retest_attainable": number(
                        value(
                            trade,
                            "recovery_pair_retest_attainable_projected_net_r",
                        )
                    ),
                    "retest_viability": str(
                        value(
                            trade,
                            "recovery_pair_retest_attainability_viability",
                        )
                        or "unknown"
                    ),
                    "aggressive_expected_bars": number(
                        value(trade, "recovery_pair_aggressive_expected_bars")
                    ),
                    "retest_expected_bars": number(
                        value(trade, "recovery_pair_retest_expected_bars")
                    ),
                    "profile_bars": number(
                        value(
                            trade,
                            "recovery_attainability_expected_bars_profile",
                        )
                    ),
                }
            )

    rows.sort(
        key=lambda row: (
            row["symbol"],
            row["timeframe"],
            row["strategy"],
            row["direction"],
        )
    )

    print()
    print("TIMEFRAME-AWARE ATTAINABILITY")
    if not rows:
        print("  No paired selector events found.")
        return

    for row in rows:
        print(f"  {row['symbol']} {row['timeframe']} {row['strategy']} {row['direction']}")
        print(
            "    Aggressive : "
            f"structural={row['aggressive_structural']} "
            f"| factor={row['aggressive_factor']} "
            f"| attainable={row['aggressive_attainable']} "
            f"| viability={row['aggressive_viability']} "
            f"| expected_bars={row['aggressive_expected_bars']}"
        )
        print(
            "    Retest     : "
            f"structural={row['retest_structural']} "
            f"| factor={row['retest_factor']} "
            f"| attainable={row['retest_attainable']} "
            f"| viability={row['retest_viability']} "
            f"| expected_bars={row['retest_expected_bars']}"
        )
        print(f"    TF profile  : {row['profile_bars']} expected bars")

    print("  Diagnostic only   : True")
    print("  Production changed: False")


_print_attainability_diagnostics()

_print_selector_diagnostics()
