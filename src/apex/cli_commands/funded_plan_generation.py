"""Generate non-authorizing funded futures-plan payloads from validated JSON inputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

import typer
from pydantic import BaseModel

from apex.application import build_funded_futures_plan_result
from apex.domain import AccountPolicy, AccountPolicyState, FuturesAccountInput
from apex.funded import ProviderPolicyBinding
from apex.risk import RiskApprovedSetup

__all__ = ["register_funded_plan_generation_commands"]

ModelT = TypeVar("ModelT", bound=BaseModel)


def register_funded_plan_generation_commands(app: typer.Typer) -> None:
    """Register deterministic funded futures-plan generation."""

    @app.command("funded-plan-generate")
    def funded_plan_generate(
        setup_path: Path = typer.Option(
            ...,
            "--setup",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Risk-approved setup JSON input.",
        ),
        account_path: Path = typer.Option(
            ...,
            "--account",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Futures account JSON input.",
        ),
        policy_path: Path = typer.Option(
            ...,
            "--policy",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Funded account-policy JSON input.",
        ),
        state_path: Path = typer.Option(
            ...,
            "--state",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Current funded account-state JSON input.",
        ),
        binding_path: Path = typer.Option(
            ...,
            "--provider-binding",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Verified provider-policy binding JSON input.",
        ),
        output_path: Path = typer.Option(
            ...,
            "--output",
            dir_okay=False,
            help="Destination funded-plan JSON result.",
        ),
        force: bool = typer.Option(False, "--force", help="Replace an existing output file."),
    ) -> None:
        """Build one non-authorizing funded futures-plan result from JSON files."""

        if output_path.exists() and not force:
            raise typer.BadParameter(f"output already exists: {output_path}")
        try:
            setup = _load_model(setup_path, RiskApprovedSetup)
            account = _load_model(account_path, FuturesAccountInput)
            policy = _load_model(policy_path, AccountPolicy)
            state = _load_model(state_path, AccountPolicyState)
            binding = _load_model(binding_path, ProviderPolicyBinding)
            result = build_funded_futures_plan_result(
                setup,
                account,
                account_policy=policy,
                account_policy_state=state,
                provider_policy_binding=binding,
            )
        except (OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        if result.get("execution_authorized") is not False:
            raise typer.BadParameter("funded plan generation must remain non-authorizing")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        eligibility = result.get("funded_eligibility")
        funded_state = eligibility.get("state") if isinstance(eligibility, dict) else "UNKNOWN"
        typer.echo(
            "FUNDED_PLAN_GENERATED "
            f"| status={result.get('status', 'UNKNOWN')} "
            f"| funded_state={funded_state} "
            "| execution_authorized=false "
            f"| output={output_path}"
        )


def _load_model(path: Path, model_type: type[ModelT]) -> ModelT:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return model_type.model_validate(payload)
