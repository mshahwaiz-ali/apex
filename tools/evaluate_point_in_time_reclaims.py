"""Evaluate sweep/reclaim entries using only decision-time-visible candles."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Any

from apex.domain.models import Candle
from apex.domain.sweep_reclaim import evaluate_sweep_reclaim
from apex.research.campaign import read_verified_campaign_resampled_klines
from apex.strategies import TradeDirection


@dataclass(frozen=True, slots=True)
class ReclaimOutcome:
    symbol: str
    direction: str
    strategy: str
    candidate_id: str
    decision_time: datetime
    reclaim_time: datetime
    event_id: str
    episode_id: str
    entry_price: float
    stop_price: float
    target_price: float
    outcome: str
    net_r: float
    bars_to_outcome: int
    same_candle_ambiguous: bool


def evaluate_reports(
    report_dir: Path,
    *,
    archive_dataset_dir: Path,
    replay_timeframe: str,
    outcome_bars: int,
    bootstrap_samples: int,
) -> dict[str, Any]:
    outcomes: list[ReclaimOutcome] = []
    for report_path in sorted(report_dir.glob("*_report.json")):
        report = _object(json.loads(report_path.read_text(encoding="utf-8")))
        symbol = str(report.get("symbol") or "")
        candles = read_verified_campaign_resampled_klines(
            archive_dataset_dir,
            symbol=symbol,
            target_timeframe=replay_timeframe,
        )
        by_close = {candle.close_time: index for index, candle in enumerate(candles)}
        shadow = _object(report.get("shadow_replay"))
        trades = shadow.get("trades")
        if not isinstance(trades, list):
            raise ValueError(f"shadow trades are unavailable: {report_path}")
        for raw_trade in trades:
            if not isinstance(raw_trade, Mapping):
                continue
            outcome = _point_in_time_outcome(
                raw_trade,
                symbol=symbol,
                candles=candles,
                by_close=by_close,
                outcome_bars=outcome_bars,
            )
            if outcome is not None:
                outcomes.append(outcome)

    unique_events = _deduplicate(outcomes, key_name="event_id")
    unique_episodes = _deduplicate(outcomes, key_name="episode_id")
    episode_metrics = _metrics(unique_episodes, bootstrap_samples=bootstrap_samples)
    folds = _chronological_folds(unique_episodes, fold_count=3, bootstrap_samples=bootstrap_samples)
    failed_gates: list[str] = []
    if len(unique_episodes) < 200:
        failed_gates.append("fewer than 200 independent market episodes")
    if _metric_float(episode_metrics, "win_rate_wilson_lower_95") < 0.50:
        failed_gates.append("95% win-rate lower bound is below 50%")
    if _metric_float(episode_metrics, "bootstrap_95_lower_bound_r") <= 0.0:
        failed_gates.append("bootstrap expectancy lower bound is not above zero")
    if not _profit_factor_above_one(episode_metrics):
        failed_gates.append("profit factor is not above one")
    if any(
        _metric_int(fold, "outcomes") < 30
        or _metric_float(fold, "net_expectancy_r") <= 0.0
        or not _profit_factor_above_one(fold)
        for fold in folds
    ):
        failed_gates.append("chronological thirds are not independently promotion-ready")

    return {
        "schema_version": 1,
        "authority": "research_only",
        "selection_timing": (
            "reclaim qualification is frozen at the reclaim candle close; "
            "outcome replay starts on the next candle"
        ),
        "lookahead_control": (
            "future deep-failure and future hold/retest facts are excluded from entry eligibility"
        ),
        "replay_timeframe": replay_timeframe,
        "outcome_horizon_bars": outcome_bars,
        "raw_qualified_entries": len(outcomes),
        "unique_geometry_events": {
            **_metrics(unique_events, bootstrap_samples=bootstrap_samples),
            "identity": "symbol_direction_strategy_reclaim_entry_stop_target",
        },
        "unique_market_episodes": {
            **episode_metrics,
            "identity": "symbol_direction_reclaim_time",
        },
        "chronological_thirds": folds,
        "by_symbol": _grouped_metrics(
            unique_episodes,
            "symbol",
            bootstrap_samples=bootstrap_samples,
        ),
        "promotion": {
            "promoted": not failed_gates,
            "failed_gates": failed_gates,
            "production_behavior_changed": False,
        },
        "outcomes": [asdict(item) for item in unique_episodes],
    }


def _point_in_time_outcome(
    trade: Mapping[str, object],
    *,
    symbol: str,
    candles: Sequence[Candle],
    by_close: Mapping[datetime, int],
    outcome_bars: int,
) -> ReclaimOutcome | None:
    metadata = _object(trade.get("metadata"))
    stop_time_raw = metadata.get("first_stop_touch_time")
    signal = _object(trade.get("signal"))
    if not isinstance(stop_time_raw, str) or not stop_time_raw or not signal:
        return None
    stop_time = datetime.fromisoformat(stop_time_raw)
    stop_index = by_close.get(stop_time)
    if stop_index is None:
        return None

    direction = TradeDirection(str(signal["direction"]))
    entry_price = _required_float(signal, "entry_price")
    stop_price = _required_float(signal, "stop_price")
    target_price = _required_float(signal, "target_price")
    maximum_confirmation_bars = 2
    assessment = None
    confirmation_count = 0
    for count in range(1, maximum_confirmation_bars + 1):
        confirmation = candles[stop_index + 1 : stop_index + 1 + count]
        if len(confirmation) != count:
            break
        current = evaluate_sweep_reclaim(
            direction=direction,
            entry_price=entry_price,
            invalidation_price=stop_price,
            target_price=target_price,
            sweep_candle=candles[stop_index],
            confirmation_candles=confirmation,
        )
        if current.reclaim_confirmed:
            assessment = current
            confirmation_count = count
            break
    if assessment is None or assessment.reclaim_entry_price is None:
        return None

    reclaim_index = stop_index + confirmation_count
    future = candles[reclaim_index + 1 : reclaim_index + 1 + outcome_bars]
    if not future:
        return None
    net_r, outcome, bars, ambiguous = _replay(
        direction=direction,
        candles=future,
        entry_price=assessment.reclaim_entry_price,
        stop_price=stop_price,
        target_price=target_price,
        metadata=metadata,
    )
    reclaim_time = candles[reclaim_index].close_time
    strategy = str(signal.get("strategy") or "")
    candidate_id = str(signal.get("candidate_id") or "")
    decision_time = datetime.fromisoformat(str(trade["decision_time"]))
    event_id = _identity(
        symbol,
        direction.value,
        strategy,
        reclaim_time.isoformat(),
        f"{assessment.reclaim_entry_price:.12g}",
        f"{stop_price:.12g}",
        f"{target_price:.12g}",
    )
    episode_id = _identity(symbol, direction.value, reclaim_time.isoformat())
    return ReclaimOutcome(
        symbol=symbol,
        direction=direction.value,
        strategy=strategy,
        candidate_id=candidate_id,
        decision_time=decision_time,
        reclaim_time=reclaim_time,
        event_id=event_id,
        episode_id=episode_id,
        entry_price=assessment.reclaim_entry_price,
        stop_price=stop_price,
        target_price=target_price,
        outcome=outcome,
        net_r=net_r,
        bars_to_outcome=bars,
        same_candle_ambiguous=ambiguous,
    )


def _replay(
    *,
    direction: TradeDirection,
    candles: Sequence[Candle],
    entry_price: float,
    stop_price: float,
    target_price: float,
    metadata: Mapping[str, object],
) -> tuple[float, str, int, bool]:
    risk = abs(entry_price - stop_price)
    entry_cost_pct = _optional_float(metadata, "configured_entry_fee_pct", 0.05) + (
        _optional_float(metadata, "configured_entry_slippage_pct", 0.02)
    )
    exit_cost_pct = _optional_float(metadata, "configured_exit_fee_pct", 0.05) + (
        _optional_float(metadata, "configured_exit_slippage_pct", 0.02)
    )

    def stop_hit(candle: Candle) -> bool:
        return (
            candle.low <= stop_price
            if direction is TradeDirection.LONG
            else candle.high >= stop_price
        )

    def target_hit(candle: Candle) -> bool:
        return (
            candle.high >= target_price
            if direction is TradeDirection.LONG
            else candle.low <= target_price
        )

    def net(exit_price: float) -> float:
        move = (
            exit_price - entry_price
            if direction is TradeDirection.LONG
            else entry_price - exit_price
        )
        costs = (
            entry_price * entry_cost_pct / 100.0 + exit_price * exit_cost_pct / 100.0
        )
        return move / risk - costs / risk

    for index, candle in enumerate(candles, start=1):
        stopped = stop_hit(candle)
        targeted = target_hit(candle)
        if stopped:
            return net(stop_price), "stop", index, targeted
        if targeted:
            return net(target_price), "target", index, False
    return net(candles[-1].close), "expired", len(candles), False


def _deduplicate(
    outcomes: Sequence[ReclaimOutcome],
    *,
    key_name: str,
) -> tuple[ReclaimOutcome, ...]:
    grouped: dict[str, list[ReclaimOutcome]] = defaultdict(list)
    for outcome in outcomes:
        grouped[str(getattr(outcome, key_name))].append(outcome)
    return tuple(
        min(
            members,
            key=lambda item: (
                item.decision_time,
                item.candidate_id,
                item.strategy,
                item.event_id,
            ),
        )
        for _, members in sorted(grouped.items())
    )


def _metrics(
    outcomes: Sequence[ReclaimOutcome],
    *,
    bootstrap_samples: int,
) -> dict[str, int | float | None]:
    values = [item.net_r for item in outcomes]
    wins = sum(value > 0.0 for value in values)
    losses = [-value for value in values if value < 0.0]
    gains = [value for value in values if value > 0.0]
    count = len(values)
    return {
        "outcomes": count,
        "wins": wins,
        "win_rate": wins / count if count else 0.0,
        "win_rate_wilson_lower_95": _wilson_lower(wins, count),
        "net_expectancy_r": fmean(values) if values else 0.0,
        "bootstrap_95_lower_bound_r": _bootstrap_lower(values, bootstrap_samples),
        "profit_factor": (
            sum(gains) / sum(losses)
            if losses
            else (None if not gains else math.inf)
        ),
        "maximum_drawdown_r": _maximum_drawdown(values),
        "same_candle_ambiguity_count": sum(
            item.same_candle_ambiguous for item in outcomes
        ),
    }


def _chronological_folds(
    outcomes: Sequence[ReclaimOutcome],
    *,
    fold_count: int,
    bootstrap_samples: int,
) -> list[dict[str, int | float | None]]:
    ordered = sorted(outcomes, key=lambda item: (item.reclaim_time, item.symbol))
    return [
        _metrics(
            ordered[len(ordered) * start // fold_count : len(ordered) * (start + 1) // fold_count],
            bootstrap_samples=bootstrap_samples,
        )
        for start in range(fold_count)
    ]


def _grouped_metrics(
    outcomes: Sequence[ReclaimOutcome],
    field: str,
    *,
    bootstrap_samples: int,
) -> dict[str, dict[str, int | float | None]]:
    groups: dict[str, list[ReclaimOutcome]] = defaultdict(list)
    for outcome in outcomes:
        groups[str(getattr(outcome, field))].append(outcome)
    return {
        key: _metrics(value, bootstrap_samples=bootstrap_samples)
        for key, value in sorted(groups.items())
    }


def _wilson_lower(wins: int, count: int) -> float:
    if count <= 0:
        return 0.0
    z = 1.959963984540054
    p = wins / count
    denominator = 1.0 + z * z / count
    center = p + z * z / (2.0 * count)
    margin = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * count)) / count)
    return (center - margin) / denominator


def _bootstrap_lower(values: Sequence[float], samples: int) -> float:
    if not values:
        return 0.0
    rng = random.Random(20260727)
    means = sorted(
        fmean(rng.choice(values) for _ in values)
        for _ in range(samples)
    )
    return means[max(0, math.ceil(samples * 0.025) - 1)]


def _maximum_drawdown(values: Sequence[float]) -> float:
    equity = 0.0
    peak = 0.0
    drawdown = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return drawdown


def _profit_factor_above_one(metrics: Mapping[str, object]) -> bool:
    value = metrics.get("profit_factor")
    return isinstance(value, int | float) and not isinstance(value, bool) and value > 1.0


def _metric_float(metrics: Mapping[str, object], key: str) -> float:
    value = metrics.get(key)
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0.0


def _metric_int(metrics: Mapping[str, object], key: str) -> int:
    value = metrics.get(key)
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0


def _required_float(values: Mapping[str, object], key: str) -> float:
    value = values.get(key)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{key} must be numeric")
    return float(value)


def _optional_float(values: Mapping[str, object], key: str, default: float) -> float:
    value = values.get(key)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return default


def _identity(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _object(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--archive-dataset-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replay-timeframe", default="5m")
    parser.add_argument("--outcome-bars", type=int, default=24)
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    args = parser.parse_args()
    result = evaluate_reports(
        args.report_dir,
        archive_dataset_dir=args.archive_dataset_dir,
        replay_timeframe=args.replay_timeframe,
        outcome_bars=args.outcome_bars,
        bootstrap_samples=args.bootstrap_samples,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    summary = {key: result[key] for key in ("promotion", "unique_market_episodes")}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
