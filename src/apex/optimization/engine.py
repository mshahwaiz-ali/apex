"""Framework-first optimization evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apex.backtesting import BacktestStudy
from apex.optimization.contracts import (
    CalibrationEvaluation,
    CandidateParameterSet,
    OptimizationDecision,
    OptimizationResult,
    OptimizationRunConfig,
    PerformanceSummary,
    WalkForwardSplit,
)


def performance_from_backtest_study(study: BacktestStudy) -> PerformanceSummary:
    """Build optimizer performance input from a reproducible backtest study."""

    report = study.report
    return PerformanceSummary(
        total_trades=report.total_trades,
        win_rate=report.win_rate,
        expectancy=report.expectancy,
        profit_factor=report.profit_factor,
        maximum_drawdown=report.maximum_drawdown,
        net_profit=report.net_profit,
        by_symbol=dict(report.by_symbol),
        by_strategy=dict(report.by_strategy),
        by_regime={},
        by_score_band={},
        by_entry_actionability={},
        loss_rate=report.loss_rate,
        average_win=report.average_win,
        average_loss=report.average_loss,
    )


def performance_from_mapping(payload: dict[str, Any]) -> PerformanceSummary:
    """Build a performance summary from a backtest/optimizer JSON payload."""

    if isinstance(payload.get("variants"), list):
        return performance_from_campaign_payload(payload)

    metrics = payload.get("metrics", payload)
    if not isinstance(metrics, dict):
        raise ValueError("performance payload must contain a metrics object")
    return PerformanceSummary(
        total_trades=int(metrics.get("total_trades", 0)),
        win_rate=float(metrics.get("win_rate", 0.0)),
        expectancy=float(metrics.get("expectancy", 0.0)),
        profit_factor=(
            None if metrics.get("profit_factor") is None else float(metrics["profit_factor"])
        ),
        maximum_drawdown=float(metrics.get("maximum_drawdown", 0.0)),
        net_profit=float(metrics.get("net_profit", 0.0)),
        by_symbol=_string_int_mapping(metrics.get("by_symbol", {})),
        by_strategy=_string_int_mapping(metrics.get("by_strategy", {})),
        by_regime=_string_int_mapping(metrics.get("by_regime", {})),
        by_score_band=_string_int_mapping(metrics.get("by_score_band", {})),
        by_entry_actionability=_string_int_mapping(
            metrics.get("by_entry_actionability", {})
        ),
        loss_rate=float(metrics.get("loss_rate", 0.0)),
        average_win=float(metrics.get("average_win", 0.0)),
        average_loss=float(metrics.get("average_loss", 0.0)),
    )


def performance_from_campaign_payload(payload: dict[str, Any]) -> PerformanceSummary:
    """Build optimizer performance from the campaign's selected best variant."""

    variants = payload.get("variants")
    if not isinstance(variants, list) or not variants:
        raise ValueError("campaign performance payload requires variants")
    best_variant = payload.get("best_variant_id")
    if not isinstance(best_variant, str) or not best_variant.strip():
        rankings = payload.get("rankings", [])
        if (
            isinstance(rankings, list)
            and rankings
            and isinstance(rankings[0], dict)
            and isinstance(rankings[0].get("variant_id"), str)
        ):
            best_variant = rankings[0]["variant_id"]
        else:
            raise ValueError("campaign performance payload requires best_variant_id")

    selected = tuple(
        item
        for item in variants
        if isinstance(item, dict)
        and isinstance(item.get("variant"), dict)
        and item["variant"].get("identifier") == best_variant
    )
    if not selected:
        raise ValueError("campaign best variant does not match any variant payload")

    total_trades = 0
    weighted_wins = 0.0
    net_profit = 0.0
    gross_profit = 0.0
    gross_loss = 0.0
    winning_trade_count = 0.0
    losing_trade_count = 0.0
    maximum_drawdown = 0.0
    by_symbol: dict[str, int] = {}
    by_strategy: dict[str, int] = {}
    by_regime: dict[str, int] = {}
    by_score_band: dict[str, int] = {}
    by_entry_actionability: dict[str, int] = {}
    for run in selected:
        metrics = run.get("metrics", {})
        if not isinstance(metrics, dict):
            continue
        trades = int(metrics.get("total_trades", 0))
        total_trades += trades
        weighted_wins += float(metrics.get("win_rate", 0.0)) * trades
        net_profit += float(metrics.get("net_profit", 0.0))
        gross_profit += float(metrics.get("gross_profit", 0.0))
        gross_loss += float(metrics.get("gross_loss", 0.0))
        winning_trade_count += float(metrics.get("win_rate", 0.0)) * trades
        losing_trade_count += float(metrics.get("loss_rate", 0.0)) * trades
        maximum_drawdown = max(maximum_drawdown, float(metrics.get("maximum_drawdown", 0.0)))
        symbol = str(run.get("symbol", ""))
        if symbol:
            by_symbol[symbol] = by_symbol.get(symbol, 0) + trades
        _merge_counts(by_symbol, metrics.get("by_symbol", {}))
        _merge_counts(by_strategy, metrics.get("by_strategy", {}))
        _merge_counts(by_regime, metrics.get("by_regime", {}))
        _merge_counts(by_score_band, metrics.get("by_score_band", {}))
        _merge_counts(
            by_entry_actionability,
            metrics.get("by_entry_actionability", {}),
        )

    profit_factor = None if gross_loss == 0.0 else gross_profit / abs(gross_loss)
    return PerformanceSummary(
        total_trades=total_trades,
        win_rate=weighted_wins / total_trades if total_trades else 0.0,
        expectancy=net_profit / total_trades if total_trades else 0.0,
        profit_factor=profit_factor,
        maximum_drawdown=maximum_drawdown,
        net_profit=net_profit,
        by_symbol=by_symbol,
        by_strategy=by_strategy,
        by_regime=by_regime,
        by_score_band=by_score_band,
        by_entry_actionability=by_entry_actionability,
        loss_rate=losing_trade_count / total_trades if total_trades else 0.0,
        average_win=gross_profit / winning_trade_count if winning_trade_count else 0.0,
        average_loss=gross_loss / losing_trade_count if losing_trade_count else 0.0,
    )


def evaluate_performance(
    summary: PerformanceSummary,
    *,
    run_config: OptimizationRunConfig,
) -> OptimizationResult:
    """Evaluate one report against an implicit zero-change baseline."""

    baseline = PerformanceSummary(
        total_trades=summary.total_trades,
        win_rate=summary.win_rate,
        expectancy=summary.expectancy,
        profit_factor=summary.profit_factor,
        maximum_drawdown=summary.maximum_drawdown,
        net_profit=summary.net_profit,
        by_symbol=dict(summary.by_symbol),
        by_strategy=dict(summary.by_strategy),
        by_regime=dict(summary.by_regime),
        by_score_band=dict(summary.by_score_band),
        by_entry_actionability=dict(summary.by_entry_actionability),
        loss_rate=summary.loss_rate,
        average_win=summary.average_win,
        average_loss=summary.average_loss,
    )
    parameter_set = CandidateParameterSet(
        identifier="current-report",
        group=run_config.variable_group,
        parameters={"report_only": True},
    )
    decision = (
        OptimizationDecision.ACCEPTED
        if summary.total_trades >= run_config.minimum_trades
        else OptimizationDecision.REJECTED
    )
    reason = (
        "report meets minimum sample size"
        if decision is OptimizationDecision.ACCEPTED
        else "report does not meet minimum sample size"
    )
    return OptimizationResult(
        decision=decision,
        run_config=run_config,
        baseline=baseline,
        candidate=summary,
        parameter_set=parameter_set,
        reasons=(reason,),
        recommended_patch={},
    )


def compare_performance(
    baseline: PerformanceSummary,
    candidate: PerformanceSummary,
    *,
    run_config: OptimizationRunConfig,
    parameter_set: CandidateParameterSet,
) -> OptimizationResult:
    """Compare candidate performance to baseline without editing production config."""

    reasons: list[str] = []
    accepted = True
    if candidate.total_trades < run_config.minimum_trades:
        accepted = False
        reasons.append("candidate does not meet minimum trade sample")
    if candidate.expectancy < baseline.expectancy + run_config.minimum_expectancy_delta:
        accepted = False
        reasons.append("candidate expectancy is not sufficiently better than baseline")
    if candidate.win_rate > baseline.win_rate and candidate.expectancy < baseline.expectancy:
        accepted = False
        reasons.append("candidate improves win rate while reducing expectancy")
    if (
        run_config.require_profit_factor_not_worse
        and baseline.profit_factor is not None
        and candidate.profit_factor is not None
        and candidate.profit_factor < baseline.profit_factor
    ):
        accepted = False
        reasons.append("candidate profit factor is worse than baseline")
    drawdown_limit = baseline.maximum_drawdown * (
        1.0 + run_config.maximum_drawdown_increase_pct / 100.0
    )
    if candidate.maximum_drawdown > drawdown_limit:
        accepted = False
        reasons.append("candidate drawdown exceeds allowed increase")
    if _exceeds_dependency_share(
        candidate.by_symbol,
        candidate.total_trades,
        run_config.maximum_symbol_trade_share,
    ):
        accepted = False
        reasons.append("candidate performance is too dependent on one symbol")
    if run_config.reject_strategy_dependency and _exceeds_dependency_share(
        candidate.by_strategy,
        candidate.total_trades,
        run_config.maximum_strategy_trade_share,
    ):
        accepted = False
        reasons.append("candidate performance is too dependent on one strategy")
    if not reasons:
        reasons.append("candidate improves or preserves required performance metrics")
    return OptimizationResult(
        decision=OptimizationDecision.ACCEPTED if accepted else OptimizationDecision.REJECTED,
        run_config=run_config,
        baseline=baseline,
        candidate=candidate,
        parameter_set=parameter_set,
        reasons=tuple(reasons),
        recommended_patch=(
            {parameter_set.group.value: dict(parameter_set.parameters)} if accepted else {}
        ),
    )


def compare_backtest_studies(
    baseline: BacktestStudy,
    candidate: BacktestStudy,
    *,
    run_config: OptimizationRunConfig,
    parameter_set: CandidateParameterSet,
) -> OptimizationResult:
    """Compare optimization candidates using actual backtest studies."""

    return compare_performance(
        performance_from_backtest_study(baseline),
        performance_from_backtest_study(candidate),
        run_config=run_config,
        parameter_set=parameter_set,
    )


def evaluate_walk_forward_calibration(
    *,
    split: WalkForwardSplit,
    run_config: OptimizationRunConfig,
    parameter_set: CandidateParameterSet,
    train_baseline: PerformanceSummary,
    train_candidate: PerformanceSummary,
    validation_baseline: PerformanceSummary,
    validation_candidate: PerformanceSummary,
    final_test_baseline: PerformanceSummary | None = None,
    final_test_candidate: PerformanceSummary | None = None,
) -> CalibrationEvaluation:
    """Evaluate train/validation performance while keeping final test isolated."""

    if run_config.split != split:
        raise ValueError("run configuration split must match calibration split")
    train = compare_performance(
        train_baseline,
        train_candidate,
        run_config=run_config,
        parameter_set=parameter_set,
    )
    validation = compare_performance(
        validation_baseline,
        validation_candidate,
        run_config=run_config,
        parameter_set=parameter_set,
    )
    accepted = (
        train.decision is OptimizationDecision.ACCEPTED
        and validation.decision is OptimizationDecision.ACCEPTED
    )
    reasons = [
        f"train={train.decision.value}",
        f"validation={validation.decision.value}",
        "final test set recorded for later audit only",
    ]
    return CalibrationEvaluation(
        split=split,
        run_config=run_config,
        parameter_set=parameter_set,
        train_result=train,
        validation_result=validation,
        final_test_baseline=final_test_baseline,
        final_test_candidate=final_test_candidate,
        final_test_used_for_selection=False,
        decision=OptimizationDecision.ACCEPTED if accepted else OptimizationDecision.REJECTED,
        reasons=tuple(reasons),
    )


def load_performance_report(path: Path) -> PerformanceSummary:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("performance report root must be an object")
    return performance_from_mapping(payload)


def save_optimization_result(result: OptimizationResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result_to_payload(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def result_to_payload(result: OptimizationResult) -> dict[str, Any]:
    return {
        "decision": result.decision.value,
        "run_config": {
            "identifier": result.run_config.identifier,
            "variable_group": result.run_config.variable_group.value,
            "minimum_trades": result.run_config.minimum_trades,
            "minimum_expectancy_delta": result.run_config.minimum_expectancy_delta,
            "maximum_drawdown_increase_pct": (result.run_config.maximum_drawdown_increase_pct),
            "require_profit_factor_not_worse": (result.run_config.require_profit_factor_not_worse),
        },
        "baseline": _summary_payload(result.baseline),
        "candidate": _summary_payload(result.candidate),
        "performance_deltas": _performance_delta_payload(
            result.baseline,
            result.candidate,
        ),
        "parameter_set": {
            "identifier": result.parameter_set.identifier,
            "group": result.parameter_set.group.value,
            "parameters": dict(result.parameter_set.parameters),
        },
        "reasons": list(result.reasons),
        "recommended_patch": dict(result.recommended_patch),
    }


def calibration_to_payload(evaluation: CalibrationEvaluation) -> dict[str, Any]:
    """Serialize walk-forward calibration decisions without mutating config."""

    return {
        "decision": evaluation.decision.value,
        "split": {
            "train_start": evaluation.split.train_start,
            "train_end": evaluation.split.train_end,
            "validation_start": evaluation.split.validation_start,
            "validation_end": evaluation.split.validation_end,
            "out_of_sample_start": evaluation.split.out_of_sample_start,
            "out_of_sample_end": evaluation.split.out_of_sample_end,
        },
        "parameter_set": {
            "identifier": evaluation.parameter_set.identifier,
            "group": evaluation.parameter_set.group.value,
            "parameters": dict(evaluation.parameter_set.parameters),
        },
        "train_result": result_to_payload(evaluation.train_result),
        "validation_result": result_to_payload(evaluation.validation_result),
        "final_test": {
            "used_for_selection": evaluation.final_test_used_for_selection,
            "baseline": (
                None
                if evaluation.final_test_baseline is None
                else _summary_payload(evaluation.final_test_baseline)
            ),
            "candidate": (
                None
                if evaluation.final_test_candidate is None
                else _summary_payload(evaluation.final_test_candidate)
            ),
        },
        "reasons": list(evaluation.reasons),
        "recommended_patch": (
            dict(evaluation.validation_result.recommended_patch)
            if evaluation.decision is OptimizationDecision.ACCEPTED
            else {}
        ),
    }


def _performance_delta_payload(
    baseline: PerformanceSummary,
    candidate: PerformanceSummary,
) -> dict[str, int | float | None]:
    """Return deterministic candidate-minus-baseline metric deltas."""

    profit_factor_delta = (
        None
        if baseline.profit_factor is None or candidate.profit_factor is None
        else _rounded_delta(candidate.profit_factor, baseline.profit_factor)
    )
    return {
        "total_trades": candidate.total_trades - baseline.total_trades,
        "win_rate": _rounded_delta(candidate.win_rate, baseline.win_rate),
        "loss_rate": _rounded_delta(candidate.loss_rate, baseline.loss_rate),
        "expectancy": _rounded_delta(candidate.expectancy, baseline.expectancy),
        "profit_factor": profit_factor_delta,
        "maximum_drawdown": _rounded_delta(
            candidate.maximum_drawdown,
            baseline.maximum_drawdown,
        ),
        "net_profit": _rounded_delta(candidate.net_profit, baseline.net_profit),
        "average_win": _rounded_delta(candidate.average_win, baseline.average_win),
        "average_loss": _rounded_delta(candidate.average_loss, baseline.average_loss),
    }


def _rounded_delta(candidate: float, baseline: float) -> float:
    return round(candidate - baseline, 6)


def _summary_payload(summary: PerformanceSummary) -> dict[str, Any]:
    return {
        "total_trades": summary.total_trades,
        "win_rate": summary.win_rate,
        "expectancy": summary.expectancy,
        "profit_factor": summary.profit_factor,
        "maximum_drawdown": summary.maximum_drawdown,
        "net_profit": summary.net_profit,
        "loss_rate": summary.loss_rate,
        "average_win": summary.average_win,
        "average_loss": summary.average_loss,
        "by_symbol": dict(summary.by_symbol),
        "by_strategy": dict(summary.by_strategy),
        "by_regime": dict(summary.by_regime),
        "by_score_band": dict(summary.by_score_band),
        "by_entry_actionability": dict(summary.by_entry_actionability),
    }


def _string_int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): int(item) for key, item in value.items()}


def _merge_counts(target: dict[str, int], value: Any) -> None:
    for key, item in _string_int_mapping(value).items():
        target[key] = target.get(key, 0) + item


def _exceeds_dependency_share(
    counts: dict[str, int],
    total: int,
    maximum_share: float,
) -> bool:
    if total <= 0 or not counts:
        return False
    return max(counts.values()) / total > maximum_share


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value
