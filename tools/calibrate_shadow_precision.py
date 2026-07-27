"""Calibrate one selective shadow-candidate rule without touching production."""

from __future__ import annotations

import argparse
import itertools
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Any

from apex.research.campaign import read_verified_campaign_resampled_klines
from apex.research.evaluation import (
    bootstrap_mean_lower_bound,
    purged_walk_forward_design,
)


@dataclass(frozen=True, slots=True)
class PrecisionCandidate:
    symbol: str
    timestamp: datetime
    net_return_r: float
    strategy: str
    source: str
    net_tp1_r: float
    cost_r: float
    alignment_score: float
    conflict_score: float
    behavior_cohort: str
    volatility_class: str
    liquidity_quote_volume_median: float
    monthly_return_cohort: str


@dataclass(frozen=True, slots=True)
class PrecisionRule:
    sources: tuple[str, ...] | None
    strategies: tuple[str, ...] | None
    minimum_net_tp1_r: float
    maximum_cost_r: float
    minimum_alignment_score: float
    maximum_conflict_score: float

    @property
    def identity(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def accepts(self, candidate: PrecisionCandidate) -> bool:
        return (
            (self.sources is None or candidate.source in self.sources)
            and (self.strategies is None or candidate.strategy in self.strategies)
            and candidate.net_tp1_r >= self.minimum_net_tp1_r
            and candidate.cost_r <= self.maximum_cost_r
            and candidate.alignment_score >= self.minimum_alignment_score
            and candidate.conflict_score <= self.maximum_conflict_score
        )


def declared_rules() -> tuple[PrecisionRule, ...]:
    source_groups: tuple[tuple[str, ...] | None, ...] = (
        None,
        ("score_or_collision_rejected",),
        (
            "score_or_collision_rejected",
            "retained_primary",
            "retained_alternative",
        ),
    )
    strategy_groups: tuple[tuple[str, ...] | None, ...] = (
        None,
        ("momentum_breakout",),
        ("trend_pullback",),
        (
            "momentum_breakout",
            "trend_pullback",
            "first_pullback_continuation",
        ),
    )
    return tuple(
        PrecisionRule(*values)
        for values in itertools.product(
            source_groups,
            strategy_groups,
            (0.0, 0.5, 1.0, 1.5),
            (0.25, 0.5, 1.0),
            (60.0, 70.0, 80.0),
            (20.0, 40.0),
        )
    )


def load_candidates(
    report_dir: Path,
    *,
    monthly_return_cohorts: Mapping[tuple[str, str], str],
) -> tuple[PrecisionCandidate, ...]:
    rows: list[PrecisionCandidate] = []
    for path in sorted(report_dir.glob("*_report.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"backtest report root must be an object: {path}")
        profiles = _profiles_by_time(payload)
        shadow = payload.get("shadow_replay")
        trades = shadow.get("trades") if isinstance(shadow, Mapping) else None
        if not isinstance(trades, list):
            raise ValueError(f"backtest report lacks shadow trades: {path}")
        for trade in trades:
            candidate = _candidate_from_trade(
                trade,
                symbol=str(payload.get("symbol") or ""),
                profiles=profiles,
                monthly_returns=monthly_return_cohorts,
            )
            if candidate is not None:
                rows.append(candidate)
    if not rows:
        raise ValueError("calibration reports contain no filled shadow candidates")
    return tuple(sorted(rows, key=lambda item: (item.timestamp, item.symbol, item.strategy)))


def calibrate(
    candidates: Sequence[PrecisionCandidate],
    *,
    bootstrap_samples: int,
) -> dict[str, Any]:
    timestamps = tuple(sorted({item.timestamp for item in candidates}))
    design = purged_walk_forward_design(
        timestamps,
        fold_count=5,
        purge_bars=1,
        embargo_bars=1,
    )
    attempts: list[dict[str, Any]] = []
    for rule in declared_rules():
        folds: list[dict[str, Any]] = []
        validation_selected: list[PrecisionCandidate] = []
        for fold in design.folds:
            selected = select_candidates(
                candidates,
                rule,
                allowed_timestamps=set(fold.validation_timestamps),
            )
            validation_selected.extend(selected)
            folds.append(metrics(selected, bootstrap_samples=bootstrap_samples))
        validation_count = sum(int(item["outcomes"]) for item in folds)
        aggregate_validation = metrics(
            validation_selected,
            bootstrap_samples=min(bootstrap_samples, 500),
        )
        positive_every_fold = all(
            int(item["outcomes"]) >= 20
            and float(item["net_expectancy_r"]) > 0.0
            and _profit_factor_above_one(item)
            for item in folds
        )
        attempts.append(
            {
                "rule": asdict(rule),
                "rule_identity": rule.identity,
                "folds": folds,
                "aggregate_validation": aggregate_validation,
                "validation_outcomes": validation_count,
                "mean_validation_win_rate": fmean(float(item["win_rate"]) for item in folds),
                "minimum_fold_win_rate": min(float(item["win_rate"]) for item in folds),
                "minimum_fold_wilson_lower_95": min(
                    float(item["win_rate_wilson_lower_95"]) for item in folds
                ),
                "mean_validation_expectancy_r": fmean(
                    float(item["net_expectancy_r"]) for item in folds
                ),
                "positive_every_fold": positive_every_fold,
            }
        )

    eligible = tuple(
        item
        for item in attempts
        if item["positive_every_fold"] is True and int(item["validation_outcomes"]) >= 100
    )
    abstention_frontier = build_abstention_frontier(attempts)
    selection_pool = eligible or tuple(attempts)
    selected_attempt = max(
        selection_pool,
        key=lambda item: (
            bool(item["positive_every_fold"]),
            float(item["minimum_fold_wilson_lower_95"]),
            float(item["mean_validation_expectancy_r"]),
            int(item["validation_outcomes"]),
            str(item["rule_identity"]),
        ),
    )
    selected_rule = PrecisionRule(**selected_attempt["rule"])
    final = select_candidates(
        candidates,
        selected_rule,
        allowed_timestamps=set(design.final_test_timestamps),
    )
    final_metrics = metrics(final, bootstrap_samples=bootstrap_samples)
    failed_gates: list[str] = []
    if not eligible:
        failed_gates.append("no rule was positive with profit factor above one in every fold")
    if _metric_int(final_metrics, "outcomes") < 200:
        failed_gates.append("fewer than 200 untouched final-test outcomes")
    if _metric_float(final_metrics, "bootstrap_95_lower_bound_r") <= 0.0:
        failed_gates.append("untouched bootstrap expectancy lower bound is not above zero")
    if not _profit_factor_above_one(final_metrics):
        failed_gates.append("untouched profit factor is not above one")
    if _metric_float(final_metrics, "win_rate_wilson_lower_95") < 0.50:
        failed_gates.append("untouched win-rate lower bound is below 50%")
    symbol_breakdown = grouped_metrics(final, "symbol")
    cohort_breakdown = grouped_metrics(final, "behavior_cohort")
    volatility_breakdown = grouped_metrics(final, "volatility_class")
    return_breakdown = grouped_metrics(final, "monthly_return_cohort")
    if any(_metric_float(item, "net_expectancy_r") <= 0.0 for item in symbol_breakdown.values()):
        failed_gates.append("untouched expectancy is not positive for every observed symbol")
    if any(_metric_float(item, "net_expectancy_r") <= 0.0 for item in cohort_breakdown.values()):
        failed_gates.append("untouched expectancy is not positive for every behavior cohort")

    return {
        "schema_version": 2,
        "authority": "research_only",
        "candidate_population": len(candidates),
        "unique_decision_timestamps": len(timestamps),
        "attempted_rules": len(attempts),
        "selection_authority": "five_purged_walk_forward_validation_folds",
        "final_test_authority": "single_untouched_20_percent_holdout",
        "selected_rule": selected_attempt,
        "eligible_rule_count": len(eligible),
        "abstention_frontier": abstention_frontier,
        "final_test": {
            **final_metrics,
            "by_symbol": symbol_breakdown,
            "by_behavior_cohort": cohort_breakdown,
            "by_volatility_class": volatility_breakdown,
            "by_monthly_return_cohort": return_breakdown,
        },
        "promotion": {
            "promoted": not failed_gates,
            "failed_gates": failed_gates,
            "authority": (
                "promoted_after_out_of_sample_validation" if not failed_gates else "research_only"
            ),
        },
        "expectation_warning": (
            "An 85-90% win rate is not a target or a gate; it is reported only if "
            "the untouched outcome population supports it after costs."
        ),
    }


def build_abstention_frontier(
    attempts: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Report the highest validation precision at useful sample floors."""

    sample_floors = (50, 100, 200)
    frontier: dict[str, object] = {}
    for minimum_outcomes in sample_floors:
        eligible = tuple(
            item
            for item in attempts
            if _nested_metric_int(item, "aggregate_validation", "outcomes") >= minimum_outcomes
        )
        if not eligible:
            frontier[str(minimum_outcomes)] = {
                "available": False,
                "reason": "no declared rule met the validation sample floor",
            }
            continue
        selected = max(
            eligible,
            key=lambda item: (
                _nested_metric_float(item, "aggregate_validation", "win_rate"),
                _nested_metric_float(
                    item,
                    "aggregate_validation",
                    "win_rate_wilson_lower_95",
                ),
                _nested_metric_float(item, "aggregate_validation", "net_expectancy_r"),
                str(item.get("rule_identity") or ""),
            ),
        )
        aggregate = selected.get("aggregate_validation")
        folds = selected.get("folds")
        fold_values = (
            tuple(item for item in folds if isinstance(item, Mapping))
            if isinstance(folds, list)
            else ()
        )
        stable_profit = bool(fold_values) and all(
            _metric_int(item, "outcomes") >= 20
            and _metric_float(item, "net_expectancy_r") > 0.0
            and _profit_factor_above_one(item)
            for item in fold_values
        )
        frontier[str(minimum_outcomes)] = {
            "available": True,
            "rule": selected.get("rule"),
            "aggregate_validation": aggregate,
            "folds": folds,
            "stable_positive_every_fold": stable_profit,
            "production_eligible": (
                stable_profit
                and isinstance(aggregate, Mapping)
                and _metric_float(aggregate, "bootstrap_95_lower_bound_r") > 0.0
                and _profit_factor_above_one(aggregate)
            ),
            "interpretation": (
                "precision research only; a higher win rate cannot override "
                "negative expectancy, fold instability, or an unseen-test requirement"
            ),
        }
    return {
        "selection_population": "purged_walk_forward_validation_only",
        "objective": "maximize_win_rate_subject_to_minimum_outcome_count",
        "frontier": frontier,
        "production_behavior_changed": False,
    }


def select_candidates(
    candidates: Sequence[PrecisionCandidate],
    rule: PrecisionRule,
    *,
    allowed_timestamps: set[datetime],
) -> tuple[PrecisionCandidate, ...]:
    selected: dict[tuple[str, datetime], PrecisionCandidate] = {}
    for candidate in candidates:
        if candidate.timestamp not in allowed_timestamps or not rule.accepts(candidate):
            continue
        key = (candidate.symbol, candidate.timestamp)
        current = selected.get(key)
        rank = (
            candidate.net_tp1_r,
            candidate.alignment_score,
            -candidate.cost_r,
            candidate.strategy,
        )
        current_rank = (
            (
                current.net_tp1_r,
                current.alignment_score,
                -current.cost_r,
                current.strategy,
            )
            if current is not None
            else None
        )
        if current_rank is None or rank > current_rank:
            selected[key] = candidate
    return tuple(selected[key] for key in sorted(selected, key=lambda item: (item[1], item[0])))


def metrics(
    candidates: Sequence[PrecisionCandidate],
    *,
    bootstrap_samples: int,
) -> dict[str, float | int | None]:
    returns = tuple(item.net_return_r for item in candidates)
    outcomes = len(returns)
    wins = sum(value > 0.0 for value in returns)
    losses = sum(value < 0.0 for value in returns)
    win_rate = wins / outcomes if outcomes else 0.0
    gross_profit = sum(value for value in returns if value > 0.0)
    gross_loss = abs(sum(value for value in returns if value < 0.0))
    average_win_r = gross_profit / wins if wins else None
    average_loss_r = gross_loss / losses if losses else None
    break_even_win_rate = (
        average_loss_r / (average_win_r + average_loss_r)
        if average_win_r is not None
        and average_loss_r is not None
        and average_win_r + average_loss_r > 0.0
        else None
    )
    return {
        "outcomes": outcomes,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "win_rate_wilson_lower_95": _wilson_lower(wins, outcomes),
        "net_expectancy_r": fmean(returns) if returns else 0.0,
        "bootstrap_95_lower_bound_r": (
            bootstrap_mean_lower_bound(returns, samples=bootstrap_samples) if returns else 0.0
        ),
        "profit_factor": gross_profit / gross_loss if gross_loss > 0.0 else None,
        "average_win_r": average_win_r,
        "average_loss_r": average_loss_r,
        "break_even_win_rate_at_observed_payoff": break_even_win_rate,
        "maximum_drawdown_r": _maximum_drawdown(returns),
    }


def grouped_metrics(
    candidates: Sequence[PrecisionCandidate],
    attribute: str,
) -> dict[str, dict[str, float | int | None]]:
    grouped: dict[str, list[PrecisionCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[str(getattr(candidate, attribute))].append(candidate)
    return {key: metrics(values, bootstrap_samples=500) for key, values in sorted(grouped.items())}


def _profiles_by_time(payload: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    records = payload.get("calibration_records")
    if not isinstance(records, list):
        return {}
    return {
        str(item["decision_time"]): item["market_profile"]
        for item in records
        if isinstance(item, Mapping)
        and isinstance(item.get("decision_time"), str)
        and isinstance(item.get("market_profile"), Mapping)
    }


def monthly_return_cohorts(
    dataset_dir: Path,
    *,
    symbols: Sequence[str],
) -> dict[tuple[str, str], str]:
    """Classify ex-post monthly return thirds for evaluation only."""

    returns_by_month: dict[str, dict[str, float]] = defaultdict(dict)
    for symbol in symbols:
        candles = read_verified_campaign_resampled_klines(
            dataset_dir,
            symbol=symbol,
            target_timeframe="1h",
        )
        closes: dict[str, list[float]] = defaultdict(list)
        for candle in candles:
            closes[candle.open_time.strftime("%Y-%m")].append(candle.close)
        for month, values in closes.items():
            if values and values[0] > 0.0:
                returns_by_month[month][symbol] = values[-1] / values[0] - 1.0

    cohorts: dict[tuple[str, str], str] = {}
    for month, monthly_values in returns_by_month.items():
        ordered = sorted(
            monthly_values,
            key=lambda item: (monthly_values[item], item),
        )
        count = len(ordered)
        for index, ordered_symbol in enumerate(ordered):
            cohort = (
                "loser" if index < count / 3 else "gainer" if index >= count * 2 / 3 else "middle"
            )
            cohorts[(ordered_symbol, month)] = cohort
    return cohorts


def _candidate_from_trade(
    trade: object,
    *,
    symbol: str,
    profiles: Mapping[str, Mapping[str, object]],
    monthly_returns: Mapping[tuple[str, str], str],
) -> PrecisionCandidate | None:
    if not isinstance(trade, Mapping):
        return None
    metadata = trade.get("metadata")
    diagnostics = trade.get("diagnostics")
    timestamp = trade.get("decision_time")
    realized = trade.get("realized_r_multiple")
    if (
        not isinstance(metadata, Mapping)
        or metadata.get("entry_filled") is not True
        or not isinstance(diagnostics, Mapping)
        or not isinstance(timestamp, str)
        or isinstance(realized, bool)
        or not isinstance(realized, int | float)
    ):
        return None
    directional = diagnostics.get("directional_snapshot")
    directional = directional if isinstance(directional, Mapping) else {}
    profile = profiles.get(timestamp, {})
    parsed_time = datetime.fromisoformat(timestamp)
    try:
        return PrecisionCandidate(
            symbol=symbol,
            timestamp=parsed_time,
            net_return_r=float(realized),
            strategy=str(metadata.get("signal_strategy") or "unknown"),
            source=str(trade.get("replay_source") or "unknown"),
            net_tp1_r=float(diagnostics["net_tp1_r"]),
            cost_r=float(diagnostics["modeled_round_trip_cost_r"]),
            alignment_score=float(directional["alignment_score"]),
            conflict_score=float(directional["conflict_score"]),
            behavior_cohort=str(profile.get("cohort") or "unknown"),
            volatility_class=str(profile.get("volatility_class") or "unknown"),
            liquidity_quote_volume_median=_optional_number(
                profile.get("liquidity_quote_volume_median")
            ),
            monthly_return_cohort=monthly_returns.get(
                (symbol, parsed_time.strftime("%Y-%m")),
                "unknown",
            ),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _profit_factor_above_one(values: Mapping[str, object]) -> bool:
    profit_factor = values.get("profit_factor")
    return isinstance(profit_factor, int | float) and float(profit_factor) > 1.0


def _metric_float(
    values: Mapping[str, float | int | None],
    key: str,
) -> float:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"calibration metric is not numeric: {key}")
    return float(value)


def _metric_int(
    values: Mapping[str, float | int | None],
    key: str,
) -> int:
    return int(_metric_float(values, key))


def _nested_metric_float(
    values: Mapping[str, object],
    nested_key: str,
    metric_key: str,
) -> float:
    nested = values.get(nested_key)
    return _metric_float(nested, metric_key) if isinstance(nested, Mapping) else 0.0


def _nested_metric_int(
    values: Mapping[str, object],
    nested_key: str,
    metric_key: str,
) -> int:
    nested = values.get(nested_key)
    return _metric_int(nested, metric_key) if isinstance(nested, Mapping) else 0


def _optional_number(value: object) -> float:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0.0


def _wilson_lower(wins: int, outcomes: int) -> float:
    if outcomes < 1:
        return 0.0
    z = 1.959963984540054
    rate = wins / outcomes
    denominator = 1.0 + z * z / outcomes
    center = rate + z * z / (2.0 * outcomes)
    margin = z * math.sqrt(rate * (1.0 - rate) / outcomes + z * z / (4.0 * outcomes * outcomes))
    return (center - margin) / denominator


def _maximum_drawdown(returns: Iterable[float]) -> float:
    equity = 0.0
    peak = 0.0
    maximum = 0.0
    for value in returns:
        equity += value
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return maximum


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--archive-dataset-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report_paths = sorted(args.report_dir.glob("*_report.json"))
    symbols = tuple(
        str(json.loads(path.read_text(encoding="utf-8")).get("symbol") or "")
        for path in report_paths
    )
    return_cohorts = monthly_return_cohorts(
        args.archive_dataset_dir,
        symbols=symbols,
    )
    report = calibrate(
        load_candidates(
            args.report_dir,
            monthly_return_cohorts=return_cohorts,
        ),
        bootstrap_samples=args.bootstrap_samples,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
