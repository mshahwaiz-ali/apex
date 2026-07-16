"""R1 CLI consuming the canonical aggregate P1 history report."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

import typer

from apex.cli_commands.readiness import (
    _checklist,
    _load_mapping,
    _mapping,
    _provider_policy_binding,
    _timestamp,
)
from apex.domain import AccountPolicyDecision, AccountPolicyType, RiskMode
from apex.execution import KillSwitchState
from apex.funded import FundedProviderLimits, evaluate_funded_readiness
from apex.validation import AggregateHistoryReason, AggregateHistoryReport


def register_funded_history_commands(app: typer.Typer) -> None:
    """Register aggregate-history-backed R1 review."""

    @app.command("funded-readiness-from-history")
    def funded_readiness_from_history(
        input_file: Path = typer.Argument(..., exists=True, dir_okay=False),
        history_review: Path = typer.Option(
            ...,
            "--history-review",
            exists=True,
            dir_okay=False,
        ),
        report: Path | None = typer.Option(None, "--report", dir_okay=False),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
    ) -> None:
        """Evaluate R1 from verified operator evidence plus aggregate P1 history."""

        try:
            payload = _load_mapping(input_file)
            result = _evaluate(payload, _load_mapping(history_review))
        except (KeyError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        serialized = _serialize(result)
        if report is not None:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(
                json.dumps(serialized, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if output == "json":
            typer.echo(json.dumps(serialized, indent=2, sort_keys=True))
            return
        reasons = ",".join(str(reason) for reason in serialized["reasons"]) or "none"
        typer.echo(
            f"FUNDED_READINESS | ready={str(serialized['ready']).lower()} "
            f"| provider={serialized['provider_name']} | reasons={reasons}"
        )


def _evaluate(payload: dict[str, Any], history: dict[str, Any]) -> object:
    provider_data = _mapping(payload, "provider_limits")
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
    aggregate = AggregateHistoryReport(
        schema_version=int(history["schema_version"]),
        generated_at=datetime.fromisoformat(str(history["generated_at"])),
        ready_for_funded_review=bool(history["ready_for_funded_review"]),
        reasons=tuple(AggregateHistoryReason(str(item)) for item in history.get("reasons", [])),
        validation_days=int(history["validation_days"]),
        total_samples=int(history["total_samples"]),
        samples_by_strategy=_int_mapping(history, "samples_by_strategy"),
        strategy_sample_shortfalls=_int_mapping(history, "strategy_sample_shortfalls"),
        consecutive_failure_free_days=int(history["consecutive_failure_free_days"]),
        mature_validation_days=int(history["mature_validation_days"]),
        ready_validation_days=int(history["ready_validation_days"]),
        ready_day_ratio=float(history["ready_day_ratio"]),
        win_rate_deterioration=float(history["win_rate_deterioration"]),
        expectancy_deterioration=float(history["expectancy_deterioration"]),
        drawdown_deterioration=float(history["drawdown_deterioration"]),
    )
    return evaluate_funded_readiness(
        provider_limits=provider_limits,
        forward_validation=aggregate,
        risk_mode=RiskMode(str(payload["risk_mode"])),
        account_policy_type=AccountPolicyType(str(payload["account_policy_type"])),
        account_policy_decision=AccountPolicyDecision.model_validate(policy_data),
        provider_policy_binding=_provider_policy_binding(payload),
        daily_lockout_verified=bool(payload["daily_lockout_verified"]),
        total_buffer_verified=bool(payload["total_buffer_verified"]),
        pre_trade_checklist=_checklist(pre_trade_data),
        post_trade_checklist=_checklist(post_trade_data),
        kill_switch_state=KillSwitchState(str(payload["kill_switch_state"])),
        generated_at=_timestamp(payload.get("generated_at")),
    )


def _int_mapping(payload: dict[str, Any], key: str) -> dict[str, int]:
    value = payload[key]
    if not isinstance(value, dict):
        raise TypeError(f"{key} must be an object")
    return {str(name): int(count) for name, count in value.items()}


def _serialize(value: object) -> dict[str, Any]:
    serialized = json.loads(json.dumps(asdict(cast(Any, value)), default=str))
    if not isinstance(serialized, dict):
        raise TypeError("report serialization must produce an object")
    return cast(dict[str, Any], serialized)


__all__ = ["register_funded_history_commands"]
