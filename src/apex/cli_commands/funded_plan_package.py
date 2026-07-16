"""Create and independently verify funded-plan evidence packages."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

import typer
import yaml
from pydantic import TypeAdapter

from apex.application.funded_futures_plan import build_funded_futures_plan_result
from apex.config import load_futures_product_config, load_strategy_approval_config
from apex.domain import AccountPolicy, AccountPolicyState, FuturesAccountInput
from apex.funded.plan_evidence_package import (
    build_funded_plan_evidence_package,
    load_and_verify_funded_plan_evidence_package,
    write_funded_plan_evidence_package,
)
from apex.funded.provider_policy_binding import ProviderPolicyBinding
from apex.risk import RiskApprovedSetup

__all__ = ["register_funded_plan_package_commands"]

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


def _summary(package_path: Path) -> str:
    package = load_and_verify_funded_plan_evidence_package(package_path)
    manifest = package.manifest
    return (
        f"provider={manifest.provider_name} "
        f"| phase={manifest.challenge_phase} "
        f"| status={manifest.plan_status} "
        f"| eligibility={manifest.funded_eligibility_state} "
        f"| package_sha256={manifest.package_sha256} "
        "| execution_authorized=false"
    )


def register_funded_plan_package_commands(app: typer.Typer) -> None:
    """Register read-only funded-plan evidence package commands."""

    @app.command("funded-plan-package")
    def funded_plan_package(
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
        output_path: Path = typer.Option(..., "--output", dir_okay=False),
        force: bool = typer.Option(False, "--force"),
    ) -> None:
        """Generate, persist, and reload one non-authorizing evidence package."""

        try:
            setup = _load_model(setup_path, RiskApprovedSetup)
            account = _load_model(account_path, FuturesAccountInput)
            policy = _load_model(policy_path, AccountPolicy)
            state = _load_model(state_path, AccountPolicyState)
            binding = _load_model(binding_path, ProviderPolicyBinding)
            futures_config = load_futures_product_config(futures_config_path)
            strategy_config = load_strategy_approval_config(strategy_config_path)
            raw_futures_config = _load_yaml_mapping(futures_config_path)
            raw_strategy_config = _load_yaml_mapping(strategy_config_path)
            funded_plan = build_funded_futures_plan_result(
                setup,
                account,
                account_policy=policy,
                account_policy_state=state,
                provider_policy_binding=binding,
                product_config=futures_config,
                strategy_approval_config=strategy_config,
            )
            package = build_funded_plan_evidence_package(
                setup=setup,
                account=account,
                account_policy=policy,
                account_state=state,
                provider_binding=binding,
                futures_config=raw_futures_config,
                strategy_approval_config=raw_strategy_config,
                funded_plan=funded_plan,
                generated_at=datetime.now(timezone.utc),
            )
            write_funded_plan_evidence_package(package, output_path, force=force)
            summary = _summary(output_path)
        except (OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(f"FUNDED_PLAN_PACKAGE_WRITTEN | {summary} | output={output_path}")

    @app.command("funded-plan-package-verify")
    def funded_plan_package_verify(
        input_path: Path = typer.Option(
            ..., "--input", exists=True, dir_okay=False, readable=True
        ),
    ) -> None:
        """Independently recompute all package hashes and consistency checks."""

        try:
            summary = _summary(input_path)
        except (OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(f"FUNDED_PLAN_PACKAGE_VERIFIED | {summary} | input={input_path}")
