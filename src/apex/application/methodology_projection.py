"""Project existing discovery setups into conservative methodology snapshots."""

from __future__ import annotations

from dataclasses import replace

from apex.application.discovery_contracts import DiscoverySetup, SymbolAnalysis
from apex.application.market_state import MarketStateSnapshot
from apex.application.market_usability import (
    MarketUsabilityAssessment,
    classify_market_usability,
)
from apex.application.methodology_contracts import TargetCandidate, TargetRole
from apex.application.methodology_market_state import adapt_market_state
from apex.application.methodology_phase5_evidence import (
    selected_candidate_methodology_evidence,
)
from apex.application.methodology_setup_maturity import derive_setup_maturity
from apex.application.methodology_snapshot import MethodologySnapshot


def project_analysis_methodology(analysis: SymbolAnalysis) -> MethodologySnapshot:
    """Return native methodology or a conservative compatibility projection.

    Compatibility projection keeps only values supported by existing contracts.
    Missing execution, invalidation, duration, confidence, and calibration metadata
    remain absent instead of being represented by fabricated defaults.
    """

    usability = classify_market_usability(analysis.data_quality_by_timeframe)
    methodology = analysis.methodology
    setup = analysis.assessment.setup
    if methodology is None:
        methodology = (
            MethodologySnapshot(market_usability=usability)
            if setup is None
            else _project_setup(setup, market_usability=usability)
        )
    else:
        updates: dict[str, object] = {}
        if methodology.market_usability is None:
            updates["market_usability"] = usability
        if methodology.direction is None and setup is not None:
            updates["direction"] = setup.direction
        if updates:
            methodology = replace(methodology, **updates)

    fused_state = getattr(analysis, "market_state", None)
    if methodology.market_state is None and isinstance(fused_state, MarketStateSnapshot):
        methodology = replace(methodology, market_state=adapt_market_state(fused_state))

    if setup is not None and not methodology.evidence:
        evidence, contradictions = selected_candidate_methodology_evidence(
            analysis.phase5_diagnostics,
            candidate_id=setup.candidate_id,
        )
        if evidence or contradictions:
            methodology = replace(
                methodology,
                evidence=evidence,
                contradictions=(
                    methodology.contradictions
                    if methodology.contradictions
                    else contradictions
                ),
            )
    return methodology


def _project_setup(
    setup: DiscoverySetup,
    *,
    market_usability: MarketUsabilityAssessment,
) -> MethodologySnapshot:
    maturity = derive_setup_maturity(setup.strategy, setup.entry_status)
    targets = tuple(
        TargetCandidate(
            role=_target_role(index, len(setup.take_profits)),
            price=target.price,
            source="; ".join(target.rationale) or "existing discovery target",
            expected_move_percentage=(
                abs(target.price - setup.entry.preferred)
                / setup.entry.preferred
                * 100.0
            ),
            risk_multiple=target.risk_reward,
            conditional=index > 2,
        )
        for index, target in enumerate(setup.take_profits, start=1)
    )
    return MethodologySnapshot(
        direction=setup.direction,
        market_usability=market_usability,
        setup_maturity=maturity.maturity,
        confirmation_policy=maturity.confirmation_policy,
        targets=targets,
    )


def _target_role(index: int, count: int) -> TargetRole:
    if index == 1:
        return TargetRole.TP1
    if index == 2:
        return TargetRole.TP2
    if index == 3 and count == 3:
        return TargetRole.TP3
    return TargetRole.RUNNER


__all__ = ["project_analysis_methodology"]
