"""Read-only reporting for funded futures-plan payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import typer

from apex.funded import FundedPlanEligibility

__all__ = ["register_funded_plan_reporting_commands"]


def register_funded_plan_reporting_commands(app: typer.Typer) -> None:
    """Register funded-plan reporting without authorizing execution."""

    @app.command("funded-plan-report")
    def funded_plan_report(
        input_path: Path = typer.Option(
            ...,
            "--input",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Funded futures-plan JSON payload to validate and report.",
        ),
        report: Path | None = typer.Option(
            None,
            "--report",
            dir_okay=False,
            help="Optional normalized JSON report path.",
        ),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
    ) -> None:
        """Validate and report a non-authorizing funded futures-plan payload."""

        payload = _load_funded_plan_payload(input_path)
        if report is not None:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        normalized_output = output.strip().lower()
        if normalized_output == "json":
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
            return
        if normalized_output != "text":
            raise typer.BadParameter("output must be text or json")
        eligibility = cast(dict[str, object], payload["funded_eligibility"])
        reasons = cast(list[object], eligibility["reasons"])
        typer.echo(
            "FUNDED_PLAN_REPORT "
            f"| status={payload.get('status', 'UNKNOWN')} "
            f"| funded_state={eligibility['state']} "
            f"| blockers={len(reasons)} "
            "| execution_authorized=false"
        )


def _load_funded_plan_payload(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise typer.BadParameter("funded plan payload must be a JSON object")
    payload = {str(key): value for key, value in raw.items()}
    if payload.get("execution_authorized") is not False:
        raise typer.BadParameter("funded plan payload must declare execution_authorized=false")
    eligibility_payload = payload.get("funded_eligibility")
    if not isinstance(eligibility_payload, dict):
        raise typer.BadParameter("funded plan payload requires funded_eligibility")
    try:
        eligibility = FundedPlanEligibility.model_validate(eligibility_payload)
    except ValueError as exc:
        raise typer.BadParameter(f"invalid funded eligibility metadata: {exc}") from exc
    if eligibility.execution_authorized is not False:
        raise typer.BadParameter("funded eligibility must remain non-authorizing")
    payload["funded_eligibility"] = eligibility.model_dump(mode="json")
    payload["execution_authorized"] = False
    return payload
