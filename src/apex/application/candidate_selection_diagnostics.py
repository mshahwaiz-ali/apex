"""Stable candidate-scoring and selection diagnostics for futures scan runs."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from apex.application.analysis import SymbolAnalysis

_ACCEPTED_OUTCOMES = frozenset({"accepted", "accepted_with_conflict_warning"})
_REJECTED_PREFIX = "rejected"


@dataclass(frozen=True, slots=True)
class CandidateSelectionDiagnosticSummary:
    """Deterministic run-level scoring and selection funnel statistics."""

    analyses_observed: int
    analyses_with_candidates: int
    analyses_selected: int
    analyses_no_trade: int
    candidates_scored: int
    candidates_ranked: int
    candidates_accepted: int
    candidates_rejected: int
    candidates_downgraded: int
    outcome_counts: Mapping[str, int]
    outcome_counts_by_strategy: Mapping[str, Mapping[str, int]]
    candidate_counts_by_strategy: Mapping[str, int]
    selected_counts_by_strategy: Mapping[str, int]
    selected_counts_by_direction: Mapping[str, int]
    no_trade_reason_counts: Mapping[str, int]
    score_band_counts: Mapping[str, int]
    score_totals_by_strategy: Mapping[str, float]
    score_observations_by_strategy: Mapping[str, int]

    def to_payload(self) -> dict[str, Any]:
        """Serialize candidate-selection analytics with deterministic ordering."""

        average_scores = {
            strategy: round(
                self.score_totals_by_strategy[strategy]
                / self.score_observations_by_strategy[strategy],
                6,
            )
            for strategy in sorted(self.score_observations_by_strategy)
            if self.score_observations_by_strategy[strategy] > 0
        }
        return {
            "analysis_funnel": {
                "observed": self.analyses_observed,
                "with_candidates": self.analyses_with_candidates,
                "selected": self.analyses_selected,
                "no_trade": self.analyses_no_trade,
            },
            "candidate_funnel": {
                "scored": self.candidates_scored,
                "ranked": self.candidates_ranked,
                "accepted": self.candidates_accepted,
                "rejected": self.candidates_rejected,
                "downgraded": self.candidates_downgraded,
            },
            "outcome_counts": _sorted_counts(self.outcome_counts),
            "outcome_counts_by_strategy": _sorted_nested_counts(
                self.outcome_counts_by_strategy
            ),
            "candidate_counts_by_strategy": _sorted_counts(
                self.candidate_counts_by_strategy
            ),
            "selected_counts_by_strategy": _sorted_counts(
                self.selected_counts_by_strategy
            ),
            "selected_counts_by_direction": _sorted_counts(
                self.selected_counts_by_direction
            ),
            "no_trade_reason_counts": _sorted_counts(self.no_trade_reason_counts),
            "score_band_counts": _ordered_score_bands(self.score_band_counts),
            "average_final_score_by_strategy": average_scores,
        }


def build_candidate_selection_diagnostic_summary(
    analyses: Sequence[SymbolAnalysis],
) -> CandidateSelectionDiagnosticSummary:
    """Aggregate stable candidate-selection fields without interpreting free-form rejection text."""

    outcome_counts: Counter[str] = Counter()
    outcomes_by_strategy: dict[str, Counter[str]] = defaultdict(Counter)
    candidate_counts: Counter[str] = Counter()
    selected_by_strategy: Counter[str] = Counter()
    selected_by_direction: Counter[str] = Counter()
    no_trade_reasons: Counter[str] = Counter()
    score_bands: Counter[str] = Counter()
    score_totals: dict[str, float] = defaultdict(float)
    score_observations: Counter[str] = Counter()

    analyses_with_candidates = analyses_selected = analyses_no_trade = 0
    scored = ranked = accepted = rejected = downgraded = 0

    for analysis in analyses:
        diagnostics = _mapping(getattr(analysis, "phase5_diagnostics", None))
        candidate_total = _non_negative_int(diagnostics.get("candidate_count"))
        ranked_total = _non_negative_int(diagnostics.get("ranked_count"))
        selected = diagnostics.get("selected") is True
        no_trade_reason = _optional_string(diagnostics.get("no_trade_reason"))
        candidates = _sequence(diagnostics.get("candidates"))

        scored += candidate_total
        ranked += ranked_total
        if candidate_total > 0:
            analyses_with_candidates += 1
        if selected:
            analyses_selected += 1
        else:
            analyses_no_trade += 1
            if no_trade_reason is not None:
                no_trade_reasons[no_trade_reason] += 1

        selected_candidate_id = _optional_string(diagnostics.get("selected_candidate_id"))
        for raw_candidate in candidates:
            candidate = _mapping(raw_candidate)
            strategy = _optional_string(candidate.get("strategy"))
            direction = _optional_string(candidate.get("direction"))
            outcome = _optional_string(candidate.get("outcome"))
            score = _finite_score(candidate.get("final_score"))
            candidate_id = _optional_string(candidate.get("candidate_id"))
            if strategy is None or outcome is None:
                continue

            candidate_counts[strategy] += 1
            outcome_counts[outcome] += 1
            outcomes_by_strategy[strategy][outcome] += 1
            if outcome in _ACCEPTED_OUTCOMES:
                accepted += 1
            elif outcome == "downgraded":
                downgraded += 1
            elif outcome.startswith(_REJECTED_PREFIX):
                rejected += 1

            if score is not None:
                band = _score_band(score)
                score_bands[band] += 1
                score_totals[strategy] += score
                score_observations[strategy] += 1

            if selected and candidate_id is not None and candidate_id == selected_candidate_id:
                selected_by_strategy[strategy] += 1
                if direction is not None:
                    selected_by_direction[direction] += 1

    return CandidateSelectionDiagnosticSummary(
        analyses_observed=len(analyses),
        analyses_with_candidates=analyses_with_candidates,
        analyses_selected=analyses_selected,
        analyses_no_trade=analyses_no_trade,
        candidates_scored=scored,
        candidates_ranked=ranked,
        candidates_accepted=accepted,
        candidates_rejected=rejected,
        candidates_downgraded=downgraded,
        outcome_counts=outcome_counts,
        outcome_counts_by_strategy=outcomes_by_strategy,
        candidate_counts_by_strategy=candidate_counts,
        selected_counts_by_strategy=selected_by_strategy,
        selected_counts_by_direction=selected_by_direction,
        no_trade_reason_counts=no_trade_reasons,
        score_band_counts=score_bands,
        score_totals_by_strategy=score_totals,
        score_observations_by_strategy=score_observations,
    )


def candidate_selection_payload(analysis: SymbolAnalysis) -> dict[str, Any]:
    """Return stable per-analysis candidate-selection diagnostics for audit records."""

    diagnostics = _mapping(getattr(analysis, "phase5_diagnostics", None))
    return {
        "symbol": analysis.symbol,
        "candidate_count": _non_negative_int(diagnostics.get("candidate_count")),
        "ranked_count": _non_negative_int(diagnostics.get("ranked_count")),
        "rejected_count": _non_negative_int(diagnostics.get("rejected_count")),
        "selected": diagnostics.get("selected") is True,
        "selected_candidate_id": diagnostics.get("selected_candidate_id"),
        "no_trade_reason": diagnostics.get("no_trade_reason"),
        "outcome_counts": dict(
            sorted(_count_candidate_outcomes(diagnostics.get("candidates")).items())
        ),
        "candidates": [
            dict(sorted(_mapping(candidate).items()))
            for candidate in _sequence(diagnostics.get("candidates"))
        ],
    }


def _count_candidate_outcomes(value: object) -> Counter[str]:
    counts: Counter[str] = Counter()
    for raw_candidate in _sequence(value):
        outcome = _optional_string(_mapping(raw_candidate).get("outcome"))
        if outcome is not None:
            counts[outcome] += 1
    return counts


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _sequence(value: object) -> tuple[object, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(value)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _non_negative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _finite_score(value: object) -> float | None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    score = float(value)
    return score if 0.0 <= score <= 100.0 else None


def _score_band(score: float) -> str:
    if score >= 85.0:
        return "85_100_exceptional"
    if score >= 75.0:
        return "75_84_strong"
    if score >= 65.0:
        return "65_74_valid_aggressive"
    if score >= 55.0:
        return "55_64_weak_experimental"
    return "below_55_rejected"


def _sorted_counts(values: Mapping[str, int]) -> dict[str, int]:
    return {key: values[key] for key in sorted(values)}


def _sorted_nested_counts(
    values: Mapping[str, Mapping[str, int]],
) -> dict[str, dict[str, int]]:
    return {
        outer: {inner: values[outer][inner] for inner in sorted(values[outer])}
        for outer in sorted(values)
    }


def _ordered_score_bands(values: Mapping[str, int]) -> dict[str, int]:
    order = (
        "85_100_exceptional",
        "75_84_strong",
        "65_74_valid_aggressive",
        "55_64_weak_experimental",
        "below_55_rejected",
    )
    return {band: values.get(band, 0) for band in order}
