"""Export machine-readable schemas for funded futures-plan workflows."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import TypeAdapter

from apex.domain import AccountPolicy, AccountPolicyState, FuturesAccountInput
from apex.funded import (
    FundedPlanAuditSummary,
    FundedPlanEligibility,
    FundedPlanEvidenceManifest,
    FundedPlanEvidencePackage,
    FundedPlanPackageIndex,
    FundedPlanPackageIndexEntry,
    FundedPlanReproductionReport,
    ProviderPolicyBinding,
)
from apex.risk import RiskApprovedSetup

__all__ = ["build_funded_plan_schema_bundle", "register_funded_plan_schema_commands"]

FUNDED_PLAN_SCHEMA_VERSION = "1.0"


def build_funded_plan_schema_bundle() -> dict[str, object]:
    """Return canonical JSON schemas for funded-plan evidence workflows."""

    return {
        "schema_version": FUNDED_PLAN_SCHEMA_VERSION,
        "execution_authorized": False,
        "schemas": {
            "setup": TypeAdapter(RiskApprovedSetup).json_schema(),
            "account": TypeAdapter(FuturesAccountInput).json_schema(),
            "policy": TypeAdapter(AccountPolicy).json_schema(),
            "state": TypeAdapter(AccountPolicyState).json_schema(),
            "provider_binding": TypeAdapter(ProviderPolicyBinding).json_schema(),
            "funded_eligibility": TypeAdapter(FundedPlanEligibility).json_schema(),
            "funded_plan_evidence_manifest": TypeAdapter(
                FundedPlanEvidenceManifest
            ).json_schema(),
            "funded_plan_evidence_package": TypeAdapter(
                FundedPlanEvidencePackage
            ).json_schema(),
            "funded_plan_reproduction_report": TypeAdapter(
                FundedPlanReproductionReport
            ).json_schema(),
            "funded_plan_audit_summary": TypeAdapter(FundedPlanAuditSummary).json_schema(),
            "funded_plan_package_index_entry": TypeAdapter(
                FundedPlanPackageIndexEntry
            ).json_schema(),
            "funded_plan_package_index": TypeAdapter(FundedPlanPackageIndex).json_schema(),
        },
    }


def register_funded_plan_schema_commands(app: typer.Typer) -> None:
    """Register funded-plan schema export without execution capability."""

    @app.command("funded-plan-schema")
    def funded_plan_schema(
        output_path: Path = typer.Option(
            ...,
            "--output",
            dir_okay=False,
            help="Destination JSON schema bundle.",
        ),
        force: bool = typer.Option(False, "--force", help="Replace an existing output file."),
    ) -> None:
        """Write canonical funded-plan schemas to one JSON file."""

        if output_path.exists() and not force:
            raise typer.BadParameter(f"output already exists: {output_path}")
        payload = build_funded_plan_schema_bundle()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        schemas = payload["schemas"]
        schema_count = len(schemas) if isinstance(schemas, dict) else 0
        typer.echo(
            "FUNDED_PLAN_SCHEMA_WRITTEN "
            f"| version={FUNDED_PLAN_SCHEMA_VERSION} "
            f"| schemas={schema_count} "
            "| execution_authorized=false "
            f"| output={output_path}"
        )
