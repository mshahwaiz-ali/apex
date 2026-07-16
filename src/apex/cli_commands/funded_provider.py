"""CLI commands for verified funded-provider limits and R1 input preparation."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated, Any, cast

import typer

from apex.config.account_policies import load_account_policies_config
from apex.funded.provider_limits_persistence import (
    load_funded_provider_limits_registry,
    write_funded_provider_limits_registry,
)
from apex.funded.provider_readiness_input import (
    prepare_funded_readiness_input,
    write_funded_readiness_input,
)


def register_funded_provider_commands(app: typer.Typer) -> None:
    """Register funded-provider registry and readiness-input commands."""

    @app.command("funded-provider-registry-normalize")
    def funded_provider_registry_normalize(
        registry: Annotated[
            Path,
            typer.Option("--registry", exists=True, dir_okay=False, readable=True),
        ],
        output: Annotated[Path, typer.Option("--output", dir_okay=False)],
        force: Annotated[bool, typer.Option("--force")] = False,
    ) -> None:
        """Validate a YAML/JSON registry and write normalized verified JSON."""

        try:
            loaded = load_funded_provider_limits_registry(registry)
            write_funded_provider_limits_registry(output, loaded, force=force)
        except (FileExistsError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(
            "FUNDED_PROVIDER_REGISTRY_NORMALIZED "
            f"| presets={len(loaded.presets)} "
            f"| maximum_age_days={loaded.maximum_verification_age_days} "
            f"| output={output}"
        )

    @app.command("funded-provider-prepare")
    def funded_provider_prepare(
        registry: Annotated[
            Path,
            typer.Option("--registry", exists=True, dir_okay=False, readable=True),
        ],
        provider_id: Annotated[str, typer.Option("--provider-id")],
        challenge_phase: Annotated[str, typer.Option("--challenge-phase")],
        as_of: Annotated[str, typer.Option("--as-of", help="YYYY-MM-DD")],
        account_policies: Annotated[
            Path,
            typer.Option("--account-policies", exists=True, dir_okay=False, readable=True),
        ],
        policy_name: Annotated[str, typer.Option("--policy")],
        template: Annotated[
            Path,
            typer.Option("--template", exists=True, dir_okay=False, readable=True),
        ],
        output: Annotated[Path, typer.Option("--output", dir_okay=False)],
        force: Annotated[bool, typer.Option("--force")] = False,
    ) -> None:
        """Prepare exact R1 input from fresh provider limits and a funded policy."""

        try:
            selected_date = date.fromisoformat(as_of)
            loaded_registry = load_funded_provider_limits_registry(registry)
            preset = loaded_registry.preset_for(
                provider_id,
                challenge_phase,
                as_of=selected_date,
            )
            policies = load_account_policies_config(account_policies)
            policy = policies.policy_for(policy_name)
            template_payload = _load_json_object(template)
            payload = prepare_funded_readiness_input(
                template_payload,
                preset=preset,
                policy=policy,
                as_of=selected_date,
                maximum_age_days=loaded_registry.maximum_verification_age_days,
            )
            write_funded_readiness_input(output, payload, force=force)
        except (FileExistsError, KeyError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "FUNDED_PROVIDER_READINESS_INPUT_PREPARED "
            f"| provider={preset.provider_name} "
            f"| phase={preset.challenge_phase} "
            f"| verified_on={preset.verified_on.isoformat()} "
            f"| preset_sha256={preset.preset_sha256 or preset.content_sha256} "
            "| execution_authorized=false "
            f"| output={output}"
        )


def _load_json_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("funded-readiness template must be a JSON object")
    return cast(dict[str, Any], value)