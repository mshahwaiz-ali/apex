"""Independent source-to-package reproduction verification for funded plans."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, TypeAdapter

from apex.funded.plan_evidence_package import (
    FundedPlanEvidencePackage,
    canonical_sha256,
    verify_funded_plan_evidence_package,
)

__all__ = [
    "FUNDED_PLAN_REPRODUCTION_SCHEMA_VERSION",
    "FundedPlanReproductionCheck",
    "FundedPlanReproductionReport",
    "FundedPlanReproductionStatus",
    "verify_funded_plan_package_reproduction",
]

FUNDED_PLAN_REPRODUCTION_SCHEMA_VERSION = "1.0"
_JSON_OBJECT = TypeAdapter(dict[str, Any])
_ANY_VALUE = TypeAdapter(Any)


class FundedPlanReproductionStatus(StrEnum):
    """Overall source-to-package reproduction outcome."""

    VERIFIED = "VERIFIED"
    MISMATCH = "MISMATCH"


class FundedPlanReproductionCheck(BaseModel):
    """One deterministic comparison between supplied and packaged evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    expected_sha256: str
    actual_sha256: str
    matches: bool


class FundedPlanReproductionReport(BaseModel):
    """Read-only result proving whether source files reproduce a packaged decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = FUNDED_PLAN_REPRODUCTION_SCHEMA_VERSION
    package_sha256: str
    provider_name: str
    challenge_phase: str
    plan_status: str
    funded_eligibility_state: str
    status: FundedPlanReproductionStatus
    checks: tuple[FundedPlanReproductionCheck, ...]
    mismatch_names: tuple[str, ...] = ()
    execution_authorized: Literal[False] = False

    @property
    def verified(self) -> bool:
        """Return whether all supplied sources exactly reproduce the package."""

        return self.status is FundedPlanReproductionStatus.VERIFIED


def _normalized(value: Any) -> dict[str, Any]:
    payload = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else _ANY_VALUE.dump_python(value, mode="json")
    )
    return _JSON_OBJECT.validate_python(payload)


def _check(name: str, expected: Mapping[str, Any], actual: Mapping[str, Any]) -> FundedPlanReproductionCheck:
    expected_sha256 = canonical_sha256(dict(expected))
    actual_sha256 = canonical_sha256(dict(actual))
    return FundedPlanReproductionCheck(
        name=name,
        expected_sha256=expected_sha256,
        actual_sha256=actual_sha256,
        matches=expected_sha256 == actual_sha256,
    )


def verify_funded_plan_package_reproduction(
    package: FundedPlanEvidencePackage | Mapping[str, object],
    *,
    setup: object,
    account: object,
    account_policy: object,
    account_state: object,
    provider_binding: object,
    futures_config: Mapping[str, object],
    strategy_approval_config: Mapping[str, object],
    regenerated_funded_plan: Mapping[str, object],
) -> FundedPlanReproductionReport:
    """Compare independent source evidence and a regenerated plan with one package."""

    verified_package = verify_funded_plan_evidence_package(package)
    if verified_package.execution_authorized is not False:
        raise ValueError("funded-plan evidence package must remain non-authorizing")

    actual_sources = {
        "setup": _normalized(setup),
        "account": _normalized(account),
        "account_policy": _normalized(account_policy),
        "account_state": _normalized(account_state),
        "provider_binding": _normalized(provider_binding),
        "futures_config": _normalized(dict(futures_config)),
        "strategy_approval_config": _normalized(dict(strategy_approval_config)),
        "funded_plan": _normalized(dict(regenerated_funded_plan)),
    }
    if actual_sources["provider_binding"].get("execution_authorized") is not False:
        raise ValueError("provider binding must remain non-authorizing")
    if actual_sources["funded_plan"].get("execution_authorized") is not False:
        raise ValueError("regenerated funded plan must remain non-authorizing")

    expected_sources = {
        "setup": verified_package.setup,
        "account": verified_package.account,
        "account_policy": verified_package.account_policy,
        "account_state": verified_package.account_state,
        "provider_binding": verified_package.provider_binding,
        "futures_config": verified_package.futures_config,
        "strategy_approval_config": verified_package.strategy_approval_config,
        "funded_plan": verified_package.funded_plan,
    }
    checks = tuple(
        _check(name, expected_sources[name], actual_sources[name])
        for name in expected_sources
    )
    mismatch_names = tuple(check.name for check in checks if not check.matches)
    status = (
        FundedPlanReproductionStatus.VERIFIED
        if not mismatch_names
        else FundedPlanReproductionStatus.MISMATCH
    )
    manifest = verified_package.manifest
    return FundedPlanReproductionReport(
        package_sha256=manifest.package_sha256,
        provider_name=manifest.provider_name,
        challenge_phase=manifest.challenge_phase,
        plan_status=manifest.plan_status,
        funded_eligibility_state=manifest.funded_eligibility_state,
        status=status,
        checks=checks,
        mismatch_names=mismatch_names,
        execution_authorized=False,
    )
