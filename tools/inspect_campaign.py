
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

    return [
        sorted(members, key=representative_key)[0]
        for members in grouped.values()
    ]


def mode_summary(
    rows: list[dict[str, Any]],
    prefix: str,
) -> dict[str, Any]:
    available = [row for row in rows if row[f"{prefix}_available"]]
    outcomes = Counter(row[f"{prefix}_outcome"] for row in available)

    net_values = [
        row[f"{prefix}_net_r"]
        for row in available
        if row[f"{prefix}_net_r"] is not None
    ]

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
            row[f"{prefix}_net_r"]
            for row in members
            if row[f"{prefix}_net_r"] is not None
        ]
        member_outcomes = Counter(
            row[f"{prefix}_outcome"]
            for row in members
        )
        speed_summary[name] = {
            "events": len(members),
            "targets": member_outcomes["target"],
            "stops": member_outcomes["stop"],
            "expired": member_outcomes["expired"],
            "average_net_r": (
                sum(member_net) / len(member_net)
                if member_net
                else None
            ),
            "total_net_r": sum(member_net),
            "gate_passes": sum(
                result >= MIN_NET_R for result in member_net
            ),
            "ambiguities": sum(
                row[f"{prefix}_ambiguous"] for row in members
            ),
        }

    count = len(available)

    return {
        "events": count,
        "targets": outcomes["target"],
        "stops": outcomes["stop"],
        "expired": outcomes["expired"],
        "target_rate": (
            outcomes["target"] / count * 100.0
            if count
            else None
        ),
        "positive_net": sum(
            row[f"{prefix}_net_r"] is not None
            and row[f"{prefix}_net_r"] > 0.0
            for row in available
        ),
        "gate_passes": sum(
            row[f"{prefix}_net_r"] is not None
            and row[f"{prefix}_net_r"] >= MIN_NET_R
            for row in available
        ),
        "ambiguities": sum(
            row[f"{prefix}_ambiguous"]
            for row in available
        ),
        "average_net_r": (
            sum(net_values) / len(net_values)
            if net_values
            else None
        ),
        "total_net_r": sum(net_values),
        "speed": speed_summary,
    }


if not POINTER.exists():
    raise SystemExit(
        "Latest campaign pointer missing. "
        "Run tools/run_11d6d_part2e_campaign.py first."
    )

run_dir = Path(POINTER.read_text().strip())

files = sorted(
    path
    for path in run_dir.glob("*.json")
    if path.name != "campaign_summary.json"
    and "inspection" not in path.name
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
    timeframe = str(
        payload.get("replay_timeframe")
        or payload.get("timeframe")
        or "unknown"
    )

    for trade in trades_from(payload):
        aggressive_available = (
            value(trade, "aggressive_reclaim_entry_available") is True
        )
        retest_available = (
            value(trade, "retest_recovery_entry_available") is True
        )

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

        aggressive_net = number(
            value(trade, "aggressive_reclaim_net_r")
        )
        retest_net = number(
            value(trade, "retest_recovery_net_r")
        )

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
                "reclaim_time": str(
                    value(trade, "recovery_reclaim_time", "")
                ),
                "event_id_strict": str(
                    value(trade, "recovery_event_id_strict", "")
                ),
                "event_id_current": str(
                    value(trade, "recovery_event_id", "")
                ),
                "event_id_loose": str(
                    value(trade, "recovery_event_id_loose", "")
                ),
                "market_episode_id": str(
                    value(trade, "recovery_market_episode_id", "")
                ),
                "event_selected": (
                    value(trade, "recovery_event_selected") is True
                ),
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

episode_ids = {
    row["market_episode_id"]
    for row in paired_rows
    if row["market_episode_id"]
}

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
print(
    "  Total difference       : "
    f"{sum(paired_deltas)}"
)

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
