"""P1 forward-validation and R1 funded-readiness CLI commands."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import typer

from apex.domain import AccountPolicyDecision, AccountPolicyType, RiskMode
from apex.execution import KillSwitchState
from apex.funded import (
    FundedProviderLimits,
    FundedReadinessReport,
    ManualExecutionChecklist,
    evaluate_funded_readiness,
)
from apex.validation import (
    ForwardValidationEvidence,
    ForwardValidationReport,
    ForwardValidationThresholds,
    ProductionEligibility,
    ValidationReason,
    evaluate_forward_validation,
)


@dataclass(frozen=True, slots=True)
class _BacktestMetrics:
    total_trades: int
    win_rate: float
    expectancy: float
    maximum_drawdown: float


@dataclass(frozen=True, slots=True)
class _PaperMetrics:
    closed_trades: int
    win_rate: float


def register_readiness_commands(app: typer.Typer) -> None:
    """Register schema-driven P1 and R1 review commands."""

    @app.command("paper-validation-review")
    def paper_validation_review(
        input_file: Path = typer.Argument(..., exists=True, dir_okay=False),
        report: Path | None = typer.Option(None, "--report", dir_okay=False),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
    ) -> None:
        """Evaluate forward paper evidence against modeled performance."""

        try:
            payload = _load_mapping(input_file)
            result = _forward_report_from_input(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        serialized = _serialize(result)
        _write_report(report, serialized)
        if output == "json":
            typer.echo(json.dumps(serialized, indent=2, sort_keys=True))
            return
        reasons = ",".join(reason.value for reason in result.reasons) or "none"
        typer.echo(
            f"PAPER_VALIDATION | eligibility={result.eligibility.value} "
            f"| closed={result.closed_paper_trades} | modeled={result.modeled_trades} "
            f"| reasons={reasons}"
        )

    @app.command("funded-readiness-review")
    def funded_readiness_review(
        input_file: Path = typer.Argument(..., exists=True, dir_okay=False),
        report: Path | None = typer.Option(None, "--report", dir_okay=False),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
    ) -> None:
        """Evaluate manual funded-account readiness from verified evidence."""

        try:
            payload = _load_mapping(input_file)
            result = _funded_report_from_input(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        serialized = _serialize(result)
        _write_report(report, serialized)
        if output == "json":
            typer.echo(json.dumps(serialized, indent=2, sort_keys=True))
            return
        reasons = ",".join(reason.value for reason in result.reasons) or "none"
        typer.echo(
            f"FUNDED_READINESS | ready={str(result.ready).lower()} "
            f"| provider={result.provider_name} | reasons={reasons}"
        )


def _forward_report_from_input(payload: dict[str, Any]) -> ForwardValidationReport:
    backtest_data = _mapping(payload, "backtest")
    paper_data = _mapping(payload, "paper")
    evidence_data = _mapping(payload, "evidence")
    thresholds_value = payload.get("thresholds", {})
    if not isinstance(thresholds_value, dict):
        raise TypeError("thresholds must be an object")
    thresholds_data = cast(dict[str, Any], thresholds_value)
    backtest = _BacktestMetrics(
        total_trades=int(backtest_data["total_trades"]),
        win_rate=float(backtest_data["win_rate"]),
        expectancy=float(backtest_data["expectancy"]),
        maximum_drawdown=float(backtest_data["maximum_drawdown"]),
    )
    paper = _PaperMetrics(
        closed_trades=int(paper_data["closed_trades"]),
        win_rate=float(paper_data["win_rate"]),
    )
    evidence = ForwardValidationEvidence(
        critical_lifecycle_failures=int(evidence_data.get("critical_lifecycle_failures", 0)),
        critical_risk_control_failures=int(evidence_data.get("critical_risk_control_failures", 0)),
        manual_instruction_failures=int(evidence_data.get("manual_instruction_failures", 0)),
        paper_expectancy=float(evidence_data["paper_expectancy"]),
        paper_maximum_drawdown=float(evidence_data["paper_maximum_drawdown"]),
    )
    thresholds = ForwardValidationThresholds(
        minimum_closed_trades=int(thresholds_data.get("minimum_closed_trades", 30)),
        maximum_win_rate_deviation=float(thresholds_data.get("maximum_win_rate_deviation", 0.15)),
        maximum_expectancy_deviation=float(
            thresholds_data.get("maximum_expectancy_deviation", 0.50)
        ),
        maximum_drawdown_increase=float(thresholds_data.get("maximum_drawdown_increase", 0.25)),
    )
    return evaluate_forward_validation(
        backtest=backtest,
        paper=paper,
        evidence=evidence,
        thresholds=thresholds,
        generated_at=_timestamp(payload.get("generated_at")),
    )


def _funded_report_from_input(payload: dict[str, Any]) -> FundedReadinessReport:
    provider_data = _mapping(payload, "provider_limits")
    validation_data = _mapping(payload, "forward_validation")
    policy_data = _mapping(payload, "account_policy_decision")
    pre_trade_data = _mapping(payload, "pre_trade_checklist")
    post_trade_data = _mapping(payload, "post_trade_checklist")
    provider_limits = FundedProviderLimits(
        provider_name=str(provider_data["provider_name"]),
        verified_on=date.fromisoformat(str(provider_data["verified_on"])),
        external_daily_drawdown_limit_pct=float(provider_data["external_daily_drawdown_limit_pct"]),
        external_total_drawdown_limit_pct=float(provider_data["external_total_drawdown_limit_pct"]),
        maximum_trades_per_day=int(provider_data["maximum_trades_per_day"]),
        limits_verified=bool(provider_data["limits_verified"]),
    )
    forward_validation = ForwardValidationReport(
        schema_version=int(validation_data["schema_version"]),
        generated_at=datetime.fromisoformat(str(validation_data["generated_at"])),
        eligibility=ProductionEligibility(str(validation_data["eligibility"])),
        reasons=tuple(ValidationReason(str(item)) for item in validation_data.get("reasons", [])),
        closed_paper_trades=int(validation_data["closed_paper_trades"]),
        modeled_trades=int(validation_data["modeled_trades"]),
        win_rate_deviation=float(validation_data["win_rate_deviation"]),
        expectancy_deviation=float(validation_data["expectancy_deviation"]),
        drawdown_increase=float(validation_data["drawdown_increase"]),
    )
    return evaluate_funded_readiness(
        provider_limits=provider_limits,
        forward_validation=forward_validation,
        risk_mode=RiskMode(str(payload["risk_mode"])),
        account_policy_type=AccountPolicyType(str(payload["account_policy_type"])),
        account_policy_decision=AccountPolicyDecision.model_validate(policy_data),
        daily_lockout_verified=bool(payload["daily_lockout_verified"]),
        total_buffer_verified=bool(payload["total_buffer_verified"]),
        pre_trade_checklist=_checklist(pre_trade_data),
        post_trade_checklist=_checklist(post_trade_data),
        kill_switch_state=KillSwitchState(str(payload["kill_switch_state"])),
        generated_at=_timestamp(payload.get("generated_at")),
    )


def _checklist(payload: dict[str, Any]) -> ManualExecutionChecklist:
    return ManualExecutionChecklist(
        analysis_reviewed=bool(payload["analysis_reviewed"]),
        risk_reviewed=bool(payload["risk_reviewed"]),
        account_state_reviewed=bool(payload["account_state_reviewed"]),
        order_or_fill_verified=bool(payload["order_or_fill_verified"]),
        lifecycle_recorded=bool(payload["lifecycle_recorded"]),
    )


def _mapping(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload[key]
    if not isinstance(value, dict):
        raise TypeError(f"{key} must be an object")
    return cast(dict[str, Any], value)


def _load_mapping(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("input document must be a JSON object")
    return cast(dict[str, Any], value)


def _timestamp(value: object) -> datetime:
    if value is None:
        return datetime.now(UTC)
    timestamp = datetime.fromisoformat(str(value))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    return timestamp


def _serialize(value: object) -> dict[str, Any]:
    serialized = json.loads(json.dumps(asdict(cast(Any, value)), default=str))
    if not isinstance(serialized, dict):
        raise TypeError("report serialization must produce an object")
    return cast(dict[str, Any], serialized)


def _write_report(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
