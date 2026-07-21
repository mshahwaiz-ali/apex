from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pytest

from apex.application.methodology_candidate_geometry_safety import (
    CandidateGeometrySafetyAudit,
)
from apex.application.methodology_candidate_routing import (
    MethodologyCandidateRoutingResult,
)
from apex.application.methodology_geometry_enforcement import (
    GeometrySafetyEnforcementUnavailableError,
    GeometrySafetyGateMode,
    apply_geometry_safety_enforcement,
)
from apex.application.methodology_geometry_safety import GeometrySafetyState
from apex.strategies.analysis import StrategyAnalysisResult
from apex.strategies.candidate_identity import candidate_identities


@dataclass(frozen=True)
class _Assessment:
    state: GeometrySafetyState
    rejection_codes: tuple[object, ...] = ()
    reasons: tuple[str, ...] = ("geometry assessment",)


@dataclass(frozen=True)
class _Audit:
    candidate_id: str
    assessment: _Assessment | None
    missing_measurements: tuple[str, ...] = ()


def _routing() -> MethodologyCandidateRoutingResult:
    from tests.unit.application.test_methodology_candidate_routing import _analysis

    analysis = _analysis()
    return cast(
        MethodologyCandidateRoutingResult,
        type(
            "_Routing",
            (),
            {
                "analysis": analysis,
                "geometry_safety_audits": (),
            },
        )(),
    )


def test_shadow_mode_never_changes_candidate_retention() -> None:
    routing = _routing()

    result = apply_geometry_safety_enforcement(
        routing,
        mode=GeometrySafetyGateMode.SHADOW,
    )

    assert result.analysis is routing.analysis
    assert result.rejected_candidate_count == 0


def test_enforcement_refuses_missing_candidate_audits() -> None:
    routing = _routing()

    with pytest.raises(
        GeometrySafetyEnforcementUnavailableError,
        match="complete retained-candidate coverage",
    ):
        apply_geometry_safety_enforcement(
            routing,
            mode=GeometrySafetyGateMode.ENFORCE,
        )


def test_enforcement_refuses_incomplete_candidate_audits() -> None:
    routing = _routing()
    identities = candidate_identities(routing.analysis.candidates)
    audits = tuple(
        cast(
            CandidateGeometrySafetyAudit,
            _Audit(candidate_id=candidate_id, assessment=None),
        )
        for candidate_id in identities
    )
    complete_shape = cast(
        MethodologyCandidateRoutingResult,
        type(
            "_Routing",
            (),
            {
                "analysis": routing.analysis,
                "geometry_safety_audits": audits,
            },
        )(),
    )

    with pytest.raises(
        GeometrySafetyEnforcementUnavailableError,
        match="incomplete audits",
    ):
        apply_geometry_safety_enforcement(
            complete_shape,
            mode=GeometrySafetyGateMode.ENFORCE,
        )


def test_enforcement_with_complete_pass_audits_preserves_candidates() -> None:
    routing = _routing()
    identities = candidate_identities(routing.analysis.candidates)
    audits = tuple(
        cast(
            CandidateGeometrySafetyAudit,
            _Audit(
                candidate_id=candidate_id,
                assessment=_Assessment(state=GeometrySafetyState.PASS),
            ),
        )
        for candidate_id in identities
    )
    complete = cast(
        MethodologyCandidateRoutingResult,
        type(
            "_Routing",
            (),
            {
                "analysis": routing.analysis,
                "geometry_safety_audits": audits,
            },
        )(),
    )

    result = apply_geometry_safety_enforcement(
        complete,
        mode=GeometrySafetyGateMode.ENFORCE,
    )

    assert isinstance(result.analysis, StrategyAnalysisResult)
    assert result.analysis.candidates == routing.analysis.candidates
    assert result.rejected_candidate_count == 0
