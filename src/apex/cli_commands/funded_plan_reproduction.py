"""Reproduce a funded-plan package from independently supplied source files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

import typer
import yaml
from pydantic import TypeAdapter

from apex.application.funded_futures_plan import build_funded_futures_plan_result
from apex.config import load_futures_product_config, load_strategy_approval_config
from apex.domain import AccountPolicy, AccountPolicyState, FuturesAccountInput
from apex.funded import (
    FundedPlanReproductionReport,
    ProviderPolicyBinding,
    load_and_verify_funded_plan_evidence_package,
    verify_funded_plan_package_reproduction,
)
from apex.risk import RiskApprovedSetup

__all__ = ["register_funded_plan_reproduction_commands"]

ModelT = TypeVar("ModelT")


def _load_model(path: Path, model_type: type[ModelT]) -> ModelT:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return TypeAdapter(model_type).validate_python(payload)


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    payload: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a YAML mapping")
    return TypeAdapter(dict[str, Any]).validate_python(payload)


def _write_report(report: FundedPlanReproductionReport, path: Path, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def register_funded_plan_reproduction_commands(app: typer.Typer) -> None:
    """Register independent source-to-package reproduction verification."""

    @app.command("funded-plan-package-reproduce")
    def funded_plan_package_reproduce(
        package_path: Path = typer.Option(..., "--package", exists=True, dir_okay=False),
        setup_path: Path = typer.Option(..., "--setup", exists=True, dir_okay=False),
        account_path: Path = typer.Option(..., "--account", exists=True, dir_okay=False),
        policy_path: Path = typer.Option(..., "--policy", exists=True, dir_okay=False),
        state_path: Path = typer.Option(..., "--state", exists=True, dir_okay=False),
        binding_path: Path = typer.Option(
            ..., "--provider-binding", exists=True, dir_okay=False
        ),
        futures_config_path: Path = typer.Option(
            ..., "--futures-config", exists=True, dir_okay=False
        ),
        strategy_config_path: Path = typer.Option(
            ..., "--strategy-config", exists=True, dir_okay=False
        ),
        report_path: Path | None = typer.Option(None, "--report", dir_okay=False),
        force: bool = typer.Option(False, "--force"),
    ) -> None:
        """Regenerate a funded plan and compare every source with an evidence package."""

        try:
            package = load_and_verify_funded_plan_evidence_package(package_path)
            setup = _load_model(setup_path, RiskApprovedSetup)
            account = _load_model(account_path, FuturesAccountInput)
            policy = _load_model(policy_path, AccountPolicy)
            state = _load_model(state_path, AccountPolicyState)
            binding = _load_model(binding_path, ProviderPolicyBinding)
            futures_config = load_futures_product_config(futures_config_path)
            strategy_config = load_strategy_approval_config(strategy_config_path)
            raw_futures_config = _load_yaml_mapping(futures_config_path)
            raw_strategy_config = _load_yaml_mapping(strategy_config_path)
            regenerated_plan = build_funded_futures_plan_result(
                setup,
                account,
                account_policy=policy,
                account_policy_state=state,
                provider_policy_binding=binding,
                product_config=futures_config,
                strategy_approval_config=strategy_config,
            )
            report = verify_funded_plan_package_reproduction(
                package,
                setup=setup,
                account=account,
                account_policy=policy,
                account_state=state,
                provider_binding=binding,
                futures_config=raw_futures_config,
                strategy_approval_config=raw_strategy_config,
                regenerated_funded_plan=regenerated_plan,
            )
            if report_path is not None:
                _write_report(report, report_path, force=force)
        except (OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        mismatch_text = ",".join(report.mismatch_names) if report.mismatch_names else "none"
        typer.echo(
            "FUNDED_PLAN_PACKAGE_REPRODUCTION "
            f"| status={report.status.value} "
            f"| provider={report.provider_name} "
            f"| phase={report.challenge_phase} "
            f"| plan_status={report.plan_status} "
            f"| eligibility={report.funded_eligibility_state} "
            f"| mismatches={mismatch_text} "
            f"| package_sha256={report.package_sha256} "
            "| execution_authorized=false"
        )
        if not report.verified:
            raise typer.Exit(code=1)
