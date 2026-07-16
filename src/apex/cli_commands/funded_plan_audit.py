"""Inspect and index verified funded-plan evidence packages."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import typer

from apex.funded import (
    build_funded_plan_audit_summary,
    build_funded_plan_package_index,
    load_and_verify_funded_plan_evidence_package,
    load_and_verify_funded_plan_package_index,
    write_funded_plan_package_index,
)

__all__ = ["register_funded_plan_audit_commands"]


def _write_json(payload: object, path: Path, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def register_funded_plan_audit_commands(app: typer.Typer) -> None:
    """Register read-only funded package audit commands."""

    @app.command("funded-plan-package-inspect")
    def funded_plan_package_inspect(
        input_path: Path = typer.Option(
            ..., "--input", exists=True, dir_okay=False, readable=True
        ),
        output_path: Path | None = typer.Option(None, "--output", dir_okay=False),
        force: bool = typer.Option(False, "--force"),
    ) -> None:
        """Verify one package and emit a redacted hash-only audit summary."""

        try:
            package = load_and_verify_funded_plan_evidence_package(input_path)
            summary = build_funded_plan_audit_summary(package)
            if output_path is not None:
                _write_json(summary, output_path, force=force)
        except (OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        reasons = ",".join(summary.funded_eligibility_reasons) or "none"
        typer.echo(
            "FUNDED_PLAN_PACKAGE_INSPECTED "
            f"| provider={summary.provider_name} "
            f"| phase={summary.challenge_phase} "
            f"| status={summary.plan_status} "
            f"| eligibility={summary.funded_eligibility_state} "
            f"| reasons={reasons} "
            f"| package_sha256={summary.package_sha256} "
            "| execution_authorized=false"
        )

    @app.command("funded-plan-package-index")
    def funded_plan_package_index(
        package_paths: list[Path] = typer.Option(
            ..., "--package", exists=True, dir_okay=False, readable=True
        ),
        output_path: Path = typer.Option(..., "--output", dir_okay=False),
        force: bool = typer.Option(False, "--force"),
    ) -> None:
        """Build and persist a deterministic index of verified packages."""

        try:
            index = build_funded_plan_package_index(
                package_paths,
                generated_at=datetime.now(timezone.utc),
            )
            write_funded_plan_package_index(index, output_path, force=force)
            verified = load_and_verify_funded_plan_package_index(output_path)
        except (OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "FUNDED_PLAN_PACKAGE_INDEX_WRITTEN "
            f"| packages={verified.package_count} "
            f"| index_sha256={verified.index_sha256} "
            "| execution_authorized=false "
            f"| output={output_path}"
        )

    @app.command("funded-plan-package-index-verify")
    def funded_plan_package_index_verify(
        input_path: Path = typer.Option(
            ..., "--input", exists=True, dir_okay=False, readable=True
        ),
    ) -> None:
        """Verify a persisted funded-plan package index."""

        try:
            index = load_and_verify_funded_plan_package_index(input_path)
        except (OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "FUNDED_PLAN_PACKAGE_INDEX_VERIFIED "
            f"| packages={index.package_count} "
            f"| index_sha256={index.index_sha256} "
            "| execution_authorized=false"
        )
