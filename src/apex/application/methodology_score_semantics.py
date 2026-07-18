"""Interpret discovery scores without turning them into probability or gate repair."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.discovery_contracts import DiscoverySetup
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class ScoreSemantics:
    """Transparent interpretation of legacy and methodology scoring."""

    available: bool
    displayed_score: float | None
    score_scale: str
    execution_blocked: bool
    execution_conditions_complete: bool
    score_can_authorize_execution: bool
    interpretation: str
    limitations: tuple[str, ...]


def derive_score_semantics(
    setup: DiscoverySetup | None,
    methodology: MethodologySnapshot,
) -> ScoreSemantics:
    """Describe score meaning while preserving earlier-stage gates.

    The legacy discovery score is retained for ranking compatibility. It cannot
    repair a hard blocker, missing execution geometry, incomplete confirmation,
    or absent historical calibration.
    """

    score = None if setup is None else float(setup.confidence_score)
    blocked = bool(methodology.hard_blockers)
    execution_complete = methodology.executable
    limitations = (
        "score is a relative analytical ranking signal",
        "score is not win probability or expected return",
        "hard blockers and incomplete execution conditions take precedence",
        "correlated evidence must not be counted as independent confirmation",
    )
    if score is None:
        interpretation = "no selected setup score is available"
    elif blocked:
        interpretation = "a displayed score cannot override explicit hard blockers"
    elif not execution_complete:
        interpretation = (
            "the score may rank a developing setup but cannot authorize execution"
        )
    else:
        interpretation = (
            "the score ranks analytical quality after required execution conditions"
        )
    return ScoreSemantics(
        available=score is not None,
        displayed_score=score,
        score_scale="legacy_relative_0_to_100",
        execution_blocked=blocked,
        execution_conditions_complete=execution_complete,
        score_can_authorize_execution=False,
        interpretation=interpretation,
        limitations=limitations,
    )


def score_semantics_payload(semantics: ScoreSemantics) -> dict[str, Any]:
    """Serialize score meaning for public output and persisted analysis."""

    return {
        "available": semantics.available,
        "displayed_score": semantics.displayed_score,
        "score_scale": semantics.score_scale,
        "execution_blocked": semantics.execution_blocked,
        "execution_conditions_complete": semantics.execution_conditions_complete,
        "score_can_authorize_execution": semantics.score_can_authorize_execution,
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


__all__ = [
    "ScoreSemantics",
    "derive_score_semantics",
    "score_semantics_payload",
]
