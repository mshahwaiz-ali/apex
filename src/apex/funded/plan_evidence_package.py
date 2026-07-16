"""Immutable funded-plan evidence packages with deterministic verification."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, TypeAdapter

from apex.funded.plan_eligibility import FundedPlanEligibility
from apex.funded.provider_policy_binding import ProviderPolicyBinding

__all__ = [
    "FUNDED_PLAN_PACKAGE_SCHEMA_VERSION",
    "FundedPlanEvidenceManifest",
    "FundedPlanEvidencePackage",
    "build_funded_plan_evidence_package",
    "canonical_sha256",
    "load_and_verify_funded_plan_evidence_package",
    "verify_funded_plan_evidence_package",
    "write_funded_plan_evidence_package",
]

FUNDED_PLAN_PACKAGE_SCHEMA_VERSION = "1.0"
_JSON_OBJECT = TypeAdapter(dict[str, Any])
_ANY_VALUE = TypeAdapter(Any)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def canonical_sha256(value: object) -> str:
    """Return the SHA-256 digest of canonical JSON-compatible data."""

    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class FundedPlanEvidenceManifest(BaseModel):
    """Hash manifest for one reproducible, explicitly non-authorizing plan decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = FUNDED_PLAN_PACKAGE_SCHEMA_VERSION
    generated_at: datetime
    setup_sha256: str
    account_input_sha256: str
    account_policy_sha256: str
    account_state_sha256: str
    provider_binding_sha256: str
    futures_config_sha256: str
    strategy_approval_config_sha256: str
    funded_plan_sha256: str
    package_sha256: str
    provider_name: str
    challenge_phase: str
    provider_preset_sha256: str
    funded_eligibility_state: str
    plan_status: str
    execution_authorized: Literal[False] = False


class FundedPlanEvidencePackage(BaseModel):
    """Normalized evidence needed to independently verify a funded-plan decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = FUNDED_PLAN_PACKAGE_SCHEMA_VERSION
    setup: dict[str, Any]
    account: dict[str, Any]
    account_policy: dict[str, Any]
    account_state: dict[str, Any]
    provider_binding: dict[str, Any]
    futures_config: dict[str, Any]
    strategy_approval_config: dict[str, Any]
    funded_plan: dict[str, Any]
    manifest: FundedPlanEvidenceManifest
    execution_authorized: Literal[False] = False


def _normalized(value: Any) -> dict[str, Any]:
    payload = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else _ANY_VALUE.dump_python(value, mode="json")
    )
    return _JSON_OBJECT.validate_python(payload)


def _unsigned_package_payload(
    *,
    setup: dict[str, Any],
    account: dict[str, Any],
    policy: dict[str, Any],
    state: dict[str, Any],
    binding: dict[str, Any],
    futures_config: dict[str, Any],
    strategy_config: dict[str, Any],
    funded_plan: dict[str, Any],
    manifest_values: Mapping[str, object],
) -> dict[str, object]:
    unsigned_manifest = dict(manifest_values)
    unsigned_manifest.pop("package_sha256", None)
    return {
        "schema_version": FUNDED_PLAN_PACKAGE_SCHEMA_VERSION,
        "setup": setup,
        "account": account,
        "account_policy": policy,
        "account_state": state,
        "provider_binding": binding,
        "futures_config": futures_config,
        "strategy_approval_config": strategy_config,
        "funded_plan": funded_plan,
        "manifest": unsigned_manifest,
        "execution_authorized": False,
    }


def build_funded_plan_evidence_package(
    *,
    setup: object,
    account: object,
    account_policy: object,
    account_state: object,
    provider_binding: ProviderPolicyBinding,
    futures_config: Mapping[str, object],
    strategy_approval_config: Mapping[str, object],
    funded_plan: Mapping[str, object],
    generated_at: datetime | None = None,
) -> FundedPlanEvidencePackage:
    """Build one normalized evidence package without introducing execution capability."""

    normalized_setup = _normalized(setup)
    normalized_account = _normalized(account)
    normalized_policy = _normalized(account_policy)
    normalized_state = _normalized(account_state)
    normalized_binding = _normalized(provider_binding)
    normalized_futures = _normalized(dict(futures_config))
    normalized_strategy = _normalized(dict(strategy_approval_config))
    normalized_plan = _normalized(dict(funded_plan))

    if normalized_binding.get("execution_authorized") is not False:
        raise ValueError("provider binding must be explicitly non-authorizing")
    if normalized_plan.get("execution_authorized") is not False:
        raise ValueError("funded plan must be explicitly non-authorizing")
    eligibility_payload = normalized_plan.get("funded_eligibility")
    eligibility = FundedPlanEligibility.model_validate(eligibility_payload)
    if eligibility.execution_authorized is not False:
        raise ValueError("funded eligibility must be explicitly non-authorizing")
    if eligibility.provider_name != provider_binding.provider_name:
        raise ValueError("funded eligibility provider does not match provider binding")
    if eligibility.challenge_phase != provider_binding.challenge_phase:
        raise ValueError("funded eligibility phase does not match provider binding")
    if eligibility.provider_preset_sha256 != provider_binding.preset_sha256:
        raise ValueError("funded eligibility preset does not match provider binding")

    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    timestamp = timestamp.astimezone(timezone.utc)
    manifest_values: dict[str, object] = {
        "schema_version": FUNDED_PLAN_PACKAGE_SCHEMA_VERSION,
        "generated_at": timestamp.isoformat().replace("+00:00", "Z"),
        "setup_sha256": canonical_sha256(normalized_setup),
        "account_input_sha256": canonical_sha256(normalized_account),
        "account_policy_sha256": canonical_sha256(normalized_policy),
        "account_state_sha256": canonical_sha256(normalized_state),
        "provider_binding_sha256": canonical_sha256(normalized_binding),
        "futures_config_sha256": canonical_sha256(normalized_futures),
        "strategy_approval_config_sha256": canonical_sha256(normalized_strategy),
        "funded_plan_sha256": canonical_sha256(normalized_plan),
        "provider_name": provider_binding.provider_name,
        "challenge_phase": provider_binding.challenge_phase,
        "provider_preset_sha256": provider_binding.preset_sha256,
        "funded_eligibility_state": eligibility.state.value,
        "plan_status": str(normalized_plan.get("status", "UNKNOWN")),
        "execution_authorized": False,
    }
    package_sha256 = canonical_sha256(
        _unsigned_package_payload(
            setup=normalized_setup,
            account=normalized_account,
            policy=normalized_policy,
            state=normalized_state,
            binding=normalized_binding,
            futures_config=normalized_futures,
            strategy_config=normalized_strategy,
            funded_plan=normalized_plan,
            manifest_values=manifest_values,
        )
    )
    manifest_values["package_sha256"] = package_sha256
    package = FundedPlanEvidencePackage(
        setup=normalized_setup,
        account=normalized_account,
        account_policy=normalized_policy,
        account_state=normalized_state,
        provider_binding=normalized_binding,
        futures_config=normalized_futures,
        strategy_approval_config=normalized_strategy,
        funded_plan=normalized_plan,
        manifest=FundedPlanEvidenceManifest.model_validate(manifest_values),
    )
    verify_funded_plan_evidence_package(package)
    return package


def verify_funded_plan_evidence_package(
    package: FundedPlanEvidencePackage | Mapping[str, object],
) -> FundedPlanEvidencePackage:
    """Recompute every digest and reject inconsistent or authorizing evidence."""

    verified = (
        package
        if isinstance(package, FundedPlanEvidencePackage)
        else FundedPlanEvidencePackage.model_validate(package)
    )
    if verified.schema_version != FUNDED_PLAN_PACKAGE_SCHEMA_VERSION:
        raise ValueError("unsupported funded-plan package schema version")
    if verified.manifest.schema_version != FUNDED_PLAN_PACKAGE_SCHEMA_VERSION:
        raise ValueError("unsupported funded-plan manifest schema version")
    if verified.execution_authorized is not False:
        raise ValueError("evidence package must be explicitly non-authorizing")
    binding = ProviderPolicyBinding.model_validate(verified.provider_binding)
    eligibility = FundedPlanEligibility.model_validate(
        verified.funded_plan.get("funded_eligibility")
    )
    if binding.execution_authorized is not False:
        raise ValueError("provider binding authorization claim rejected")
    if eligibility.execution_authorized is not False:
        raise ValueError("funded eligibility authorization claim rejected")
    if verified.funded_plan.get("execution_authorized") is not False:
        raise ValueError("funded plan authorization claim rejected")

    manifest = verified.manifest
    expected_hashes = {
        "setup_sha256": canonical_sha256(verified.setup),
        "account_input_sha256": canonical_sha256(verified.account),
        "account_policy_sha256": canonical_sha256(verified.account_policy),
        "account_state_sha256": canonical_sha256(verified.account_state),
        "provider_binding_sha256": canonical_sha256(verified.provider_binding),
        "futures_config_sha256": canonical_sha256(verified.futures_config),
        "strategy_approval_config_sha256": canonical_sha256(
            verified.strategy_approval_config
        ),
        "funded_plan_sha256": canonical_sha256(verified.funded_plan),
    }
    for field_name, expected in expected_hashes.items():
        if getattr(manifest, field_name) != expected:
            raise ValueError(f"evidence hash mismatch: {field_name}")

    if manifest.provider_name != binding.provider_name:
        raise ValueError("manifest provider does not match provider binding")
    if manifest.challenge_phase != binding.challenge_phase:
        raise ValueError("manifest phase does not match provider binding")
    if manifest.provider_preset_sha256 != binding.preset_sha256:
        raise ValueError("manifest preset does not match provider binding")
    if eligibility.provider_name != binding.provider_name:
        raise ValueError("funded eligibility provider does not match provider binding")
    if eligibility.challenge_phase != binding.challenge_phase:
        raise ValueError("funded eligibility phase does not match provider binding")
    if eligibility.provider_preset_sha256 != binding.preset_sha256:
        raise ValueError("funded eligibility preset does not match provider binding")
    if manifest.funded_eligibility_state != eligibility.state.value:
        raise ValueError("manifest funded eligibility state mismatch")
    if manifest.plan_status != str(verified.funded_plan.get("status", "UNKNOWN")):
        raise ValueError("manifest plan status mismatch")

    manifest_values = manifest.model_dump(mode="json")
    expected_package_hash = canonical_sha256(
        _unsigned_package_payload(
            setup=verified.setup,
            account=verified.account,
            policy=verified.account_policy,
            state=verified.account_state,
            binding=verified.provider_binding,
            futures_config=verified.futures_config,
            strategy_config=verified.strategy_approval_config,
            funded_plan=verified.funded_plan,
            manifest_values=manifest_values,
        )
    )
    if manifest.package_sha256 != expected_package_hash:
        raise ValueError("evidence package hash mismatch")
    return verified


def write_funded_plan_evidence_package(
    package: FundedPlanEvidencePackage,
    path: Path,
    *,
    force: bool = False,
) -> None:
    """Persist stable JSON with overwrite protection and a terminal newline."""

    verify_funded_plan_evidence_package(package)
    if path.exists() and not force:
        raise FileExistsError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(package.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_and_verify_funded_plan_evidence_package(path: Path) -> FundedPlanEvidencePackage:
    """Load one JSON package and independently verify its complete hash boundary."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return verify_funded_plan_evidence_package(payload)
