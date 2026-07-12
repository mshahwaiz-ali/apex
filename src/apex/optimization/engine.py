"""Framework-first Phase 10 optimization evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apex.backtesting import BacktestStudy
from apex.optimization.contracts import (
    CandidateParameterSet,
    OptimizationDecision,
    OptimizationResult,
    OptimizationRunConfig,
    PerformanceSummary,
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
    )


def performance_from_mapping(payload: dict[str, Any]) -> PerformanceSummary:
    """Build a performance summary from a backtest/optimizer JSON payload."""

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
        "parameter_set": {
            "identifier": result.parameter_set.identifier,
            "group": result.parameter_set.group.value,
            "parameters": dict(result.parameter_set.parameters),
        },
        "reasons": list(result.reasons),
        "recommended_patch": dict(result.recommended_patch),
    }


def _summary_payload(summary: PerformanceSummary) -> dict[str, Any]:
    return {
        "total_trades": summary.total_trades,
        "win_rate": summary.win_rate,
        "expectancy": summary.expectancy,
        "profit_factor": summary.profit_factor,
        "maximum_drawdown": summary.maximum_drawdown,
        "net_profit": summary.net_profit,
        "by_symbol": dict(summary.by_symbol),
        "by_strategy": dict(summary.by_strategy),
        "by_regime": dict(summary.by_regime),
        "by_score_band": dict(summary.by_score_band),
    }


def _string_int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): int(item) for key, item in value.items()}


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
