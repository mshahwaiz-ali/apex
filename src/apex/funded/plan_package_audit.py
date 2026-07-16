"""Read-only audit summaries and deterministic indexes for funded-plan packages."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from apex.funded.plan_evidence_package import (
    FundedPlanEvidencePackage,
    canonical_sha256,
    load_and_verify_funded_plan_evidence_package,
)

__all__ = [
    "FUNDED_PLAN_AUDIT_SCHEMA_VERSION",
    "FUNDED_PLAN_INDEX_SCHEMA_VERSION",
    "FundedPlanAuditSummary",
    "FundedPlanPackageIndex",
    "FundedPlanPackageIndexEntry",
    "build_funded_plan_audit_summary",
    "build_funded_plan_package_index",
    "load_and_verify_funded_plan_package_index",
    "write_funded_plan_package_index",
]

FUNDED_PLAN_AUDIT_SCHEMA_VERSION = "1.0"
FUNDED_PLAN_INDEX_SCHEMA_VERSION = "1.0"


class FundedPlanAuditSummary(BaseModel):
    """Redacted operational summary of one verified evidence package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = FUNDED_PLAN_AUDIT_SCHEMA_VERSION
    package_sha256: str
    generated_at: datetime
    provider_name: str
    challenge_phase: str
    provider_preset_sha256: str
    plan_status: str
    funded_eligibility_state: str
    funded_eligibility_reasons: tuple[str, ...] = ()
    setup_sha256: str
    account_input_sha256: str
    account_policy_sha256: str
    account_state_sha256: str
    provider_binding_sha256: str
    futures_config_sha256: str
    strategy_approval_config_sha256: str
    funded_plan_sha256: str
    execution_authorized: Literal[False] = False


class FundedPlanPackageIndexEntry(BaseModel):
    """Stable searchable identity for one verified funded-plan package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    package_path: str
    package_sha256: str
    generated_at: datetime
    provider_name: str
    challenge_phase: str
    provider_preset_sha256: str
    plan_status: str
    funded_eligibility_state: str
    execution_authorized: Literal[False] = False


class FundedPlanPackageIndex(BaseModel):
    """Deterministic read-only index of verified funded-plan packages."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = FUNDED_PLAN_INDEX_SCHEMA_VERSION
    generated_at: datetime
    package_count: int
    entries: tuple[FundedPlanPackageIndexEntry, ...]
    index_sha256: str
    execution_authorized: Literal[False] = False


def build_funded_plan_audit_summary(
    package: FundedPlanEvidencePackage,
) -> FundedPlanAuditSummary:
    """Build a secret-free summary from one already verified package."""

    manifest = package.manifest
    eligibility = package.funded_plan.get("funded_eligibility")
    reasons: tuple[str, ...] = ()
    if isinstance(eligibility, dict):
        raw_reasons = eligibility.get("reasons", ())
        if isinstance(raw_reasons, (list, tuple)):
            reasons = tuple(str(reason) for reason in raw_reasons)
    return FundedPlanAuditSummary(
        package_sha256=manifest.package_sha256,
        generated_at=manifest.generated_at,
        provider_name=manifest.provider_name,
        challenge_phase=manifest.challenge_phase,
        provider_preset_sha256=manifest.provider_preset_sha256,
        plan_status=manifest.plan_status,
        funded_eligibility_state=manifest.funded_eligibility_state,
        funded_eligibility_reasons=reasons,
        setup_sha256=manifest.setup_sha256,
        account_input_sha256=manifest.account_input_sha256,
        account_policy_sha256=manifest.account_policy_sha256,
        account_state_sha256=manifest.account_state_sha256,
        provider_binding_sha256=manifest.provider_binding_sha256,
        futures_config_sha256=manifest.futures_config_sha256,
        strategy_approval_config_sha256=manifest.strategy_approval_config_sha256,
        funded_plan_sha256=manifest.funded_plan_sha256,
        execution_authorized=False,
    )


def _index_entry(path: Path, package: FundedPlanEvidencePackage) -> FundedPlanPackageIndexEntry:
    manifest = package.manifest
    return FundedPlanPackageIndexEntry(
        package_path=path.as_posix(),
        package_sha256=manifest.package_sha256,
        generated_at=manifest.generated_at,
        provider_name=manifest.provider_name,
        challenge_phase=manifest.challenge_phase,
        provider_preset_sha256=manifest.provider_preset_sha256,
        plan_status=manifest.plan_status,
        funded_eligibility_state=manifest.funded_eligibility_state,
        execution_authorized=False,
    )


def _index_hash_payload(
    *, generated_at: datetime, entries: tuple[FundedPlanPackageIndexEntry, ...]
) -> dict[str, object]:
    return {
        "schema_version": FUNDED_PLAN_INDEX_SCHEMA_VERSION,
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "package_count": len(entries),
        "entries": [entry.model_dump(mode="json") for entry in entries],
        "execution_authorized": False,
    }


def build_funded_plan_package_index(
    package_paths: list[Path],
    *,
    generated_at: datetime | None = None,
) -> FundedPlanPackageIndex:
    """Load, verify, de-duplicate, and index funded-plan packages."""

    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    timestamp = timestamp.astimezone(timezone.utc)

    entries_by_hash: dict[str, FundedPlanPackageIndexEntry] = {}
    for path in sorted(package_paths, key=lambda item: item.as_posix()):
        package = load_and_verify_funded_plan_evidence_package(path)
        entry = _index_entry(path, package)
        existing = entries_by_hash.get(entry.package_sha256)
        if existing is not None and existing.package_path != entry.package_path:
            raise ValueError(
                "duplicate funded-plan package hash across paths: "
                f"{existing.package_path}, {entry.package_path}"
            )
        entries_by_hash[entry.package_sha256] = entry

    entries = tuple(
        sorted(
            entries_by_hash.values(),
            key=lambda entry: (
                entry.generated_at,
                entry.provider_name.casefold(),
                entry.challenge_phase.casefold(),
                entry.package_sha256,
            ),
        )
    )
    hash_payload = _index_hash_payload(generated_at=timestamp, entries=entries)
    return FundedPlanPackageIndex(
        generated_at=timestamp,
        package_count=len(entries),
        entries=entries,
        index_sha256=canonical_sha256(hash_payload),
        execution_authorized=False,
    )


def _verify_index(index: FundedPlanPackageIndex) -> FundedPlanPackageIndex:
    if index.schema_version != FUNDED_PLAN_INDEX_SCHEMA_VERSION:
        raise ValueError("unsupported funded-plan package index schema version")
    if index.execution_authorized is not False:
        raise ValueError("funded-plan package index must remain non-authorizing")
    if index.package_count != len(index.entries):
        raise ValueError("funded-plan package index count mismatch")
    if len({entry.package_sha256 for entry in index.entries}) != len(index.entries):
        raise ValueError("funded-plan package index contains duplicate package hashes")
    expected = canonical_sha256(
        _index_hash_payload(generated_at=index.generated_at, entries=index.entries)
    )
    if index.index_sha256 != expected:
        raise ValueError("funded-plan package index hash mismatch")
    return index


def write_funded_plan_package_index(
    index: FundedPlanPackageIndex,
    path: Path,
    *,
    force: bool = False,
) -> None:
    """Persist a deterministic verified index with overwrite protection."""

    _verify_index(index)
    if path.exists() and not force:
        raise FileExistsError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(index.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_and_verify_funded_plan_package_index(path: Path) -> FundedPlanPackageIndex:
    """Load and verify a deterministic funded-plan package index."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return _verify_index(FundedPlanPackageIndex.model_validate(payload))
