"""Shared canonical opportunity selection for live and historical consumers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from apex.application.discovery_contracts import DiscoverySetup
from apex.application.opportunity_portfolio import (
    ActionabilityState,
    SequenceRole,
    build_actionability_state_assessment,
)


@dataclass(frozen=True, slots=True)
class CanonicalOpportunityDecision:
    """One canonical portfolio decision independent of CLI presentation mode."""

    setup: DiscoverySetup | None
    opportunity_id: str | None
    sequence_role: str | None
    lane: str | None
    actionability_state: str | None
    reason_code: str
    canonical_portfolio: bool
    execution_authorized: bool = False


_EXECUTABLE_STATES = frozenset(
    {
        ActionabilityState.EXECUTE_NOW,
        ActionabilityState.AGGRESSIVE_NOW,
    }
)


def select_canonical_opportunity_decision(
    analysis: object,
) -> CanonicalOpportunityDecision:
    """Select the same immediate or future setup for every analysis consumer."""

    portfolio = getattr(analysis, "opportunity_portfolio", None)
    if portfolio is None:
        assessment = getattr(analysis, "assessment", None)
        setup = getattr(assessment, "setup", None)
        return CanonicalOpportunityDecision(
            setup=setup if isinstance(setup, DiscoverySetup) else None,
            opportunity_id=(setup.candidate_id if isinstance(setup, DiscoverySetup) else None),
            sequence_role=(
                SequenceRole.CURRENT.value if isinstance(setup, DiscoverySetup) else None
            ),
            lane=None,
            actionability_state=None,
            reason_code=(
                "legacy_selected_setup"
                if isinstance(setup, DiscoverySetup)
                else "legacy_no_selected_setup"
            ),
            canonical_portfolio=False,
            execution_authorized=(
                isinstance(setup, DiscoverySetup) and setup.execution_allowed_now
            ),
        )

    observed_states: list[ActionabilityState] = []
    pending_decision: CanonicalOpportunityDecision | None = None
    opportunities = tuple(getattr(portfolio, "opportunities", ()))
    for opportunity in opportunities:
        setup = getattr(opportunity, "setup", None)
        role = getattr(opportunity, "sequence_role", None)
        if not isinstance(setup, DiscoverySetup) or not isinstance(role, SequenceRole):
            continue

        actionability = build_actionability_state_assessment(
            setup,
            sequence_role=role,
        )
        observed_states.append(actionability.state)
        opportunity_id = str(getattr(opportunity, "opportunity_id", setup.candidate_id))
        lane = _enum_value(
            getattr(
                opportunity,
                "effective_lane",
                getattr(opportunity, "lane", None),
            )
        )

        if (
            role is SequenceRole.CURRENT
            and actionability.state in _EXECUTABLE_STATES
            and setup.execution_allowed_now
            and not actionability.has_blocking_issue
        ):
            return CanonicalOpportunityDecision(
                setup=setup,
                opportunity_id=opportunity_id,
                sequence_role=role.value,
                lane=lane,
                actionability_state=actionability.state.value,
                reason_code="canonical_executable_opportunity",
                canonical_portfolio=True,
                execution_authorized=True,
            )

        if (
            pending_decision is None
            and setup.conditional_plan is not None
            and actionability.state
            not in {
                ActionabilityState.MISSED_OR_CHASING,
                ActionabilityState.INVALIDATED,
            }
        ):
            pending_decision = CanonicalOpportunityDecision(
                setup=setup,
                opportunity_id=opportunity_id,
                sequence_role=role.value,
                lane=lane,
                actionability_state=actionability.state.value,
                reason_code="canonical_opportunity_pending_activation",
                canonical_portfolio=True,
                execution_authorized=False,
            )

    if pending_decision is not None:
        return pending_decision

    reason_code = "canonical_no_executable_opportunity"
    if ActionabilityState.MISSED_OR_CHASING in observed_states:
        reason_code = "canonical_opportunity_missed_or_chasing"
    elif ActionabilityState.INVALIDATED in observed_states:
        reason_code = "canonical_opportunity_invalidated"
    elif observed_states:
        reason_code = "canonical_opportunity_pending_activation"

    return CanonicalOpportunityDecision(
        setup=None,
        opportunity_id=None,
        sequence_role=None,
        lane=None,
        actionability_state=None,
        reason_code=reason_code,
        canonical_portfolio=True,
    )


def _enum_value(value: object) -> str | None:
    if isinstance(value, Enum):
        return str(value.value)
    return value if isinstance(value, str) else None


__all__ = [
    "CanonicalOpportunityDecision",
    "select_canonical_opportunity_decision",
]
