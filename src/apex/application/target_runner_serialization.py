"""Canonical JSON-safe target and runner diagnostics for discovery outputs."""

from __future__ import annotations

from typing import Any

from apex.application.discovery_contracts import (
    DiscoveryAssessment,
    DiscoverySetup,
    ManagementPolicy,
    TakeProfit,
)


def serialize_take_profit(target: TakeProfit) -> dict[str, Any]:
    """Serialize one target without inventing omitted target evidence."""

    return {
        "label": target.label,
        "price": target.price,
        "reward": target.reward,
        "risk_reward": target.risk_reward,
        "partial_close_pct": target.partial_close_pct,
        "target_type": target.target_type.value,
        "purpose": target.purpose,
        "target_basis": target.target_basis,
        "target_timeframe": target.target_timeframe,
        "target_role": target.target_role.value,
        "synthetic": target.synthetic,
        "runner_qualified": target.runner_qualified,
        "rationale": list(target.rationale),
    }


def serialize_management_policy(policy: ManagementPolicy) -> dict[str, Any]:
    """Serialize one lifecycle policy in deterministic field order."""

    return {
        "kind": policy.kind.value,
        "trigger": policy.trigger,
        "action": policy.action,
        "rationale": list(policy.rationale),
    }


def serialize_setup_target_runner_diagnostics(
    setup: DiscoverySetup,
) -> dict[str, Any]:
    """Serialize the canonical setup target hierarchy and runner authority."""

    return {
        "candidate_id": setup.candidate_id,
        "runner_qualified": setup.runner_qualified,
        "runner_qualification_reason": setup.runner_qualification_reason,
        "targets": [serialize_take_profit(target) for target in setup.take_profits],
        "management_policies": [
            serialize_management_policy(policy) for policy in setup.management_policies
        ],
    }


def serialize_assessment_target_runner_diagnostics(
    assessment: DiscoveryAssessment,
) -> dict[str, Any]:
    """Serialize selected/developing setups through one mode-neutral path."""

    return {
        "symbol": assessment.symbol,
        "selected_setup": (
            None
            if assessment.setup is None
            else serialize_setup_target_runner_diagnostics(assessment.setup)
        ),
        "developing_setup": (
            None
            if assessment.developing_setup is None
            else serialize_setup_target_runner_diagnostics(assessment.developing_setup)
        ),
    }


__all__ = [
    "serialize_assessment_target_runner_diagnostics",
    "serialize_management_policy",
    "serialize_setup_target_runner_diagnostics",
    "serialize_take_profit",
]
