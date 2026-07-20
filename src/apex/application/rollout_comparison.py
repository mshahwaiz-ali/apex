"""Non-authoritative old-versus-new rollout diagnostics.

The comparator operates on already serialized deterministic analysis payloads.
It reports differences only; it does not select, rank, suppress, promote, or
otherwise mutate either result.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

_MISSING = object()
_PORTFOLIO_SLOT_KEYS = (
    "current_long",
    "current_short",
    "nearby_long",
    "nearby_short",
    "runner_plan",
)


@dataclass(frozen=True, slots=True)
class DiagnosticDifference:
    """One stable field-level difference between legacy and new outputs."""

    field: str
    legacy: Any
    new: Any


@dataclass(frozen=True, slots=True)
class AnalysisComparisonReport:
    """Deterministic, non-authoritative comparison of two distinct projections."""

    symbol: str | None
    legacy_opportunity_count: int
    new_opportunity_count: int
    differences: tuple[DiagnosticDifference, ...]
    legacy_projection_kind: str = "legacy_single_winner"
    new_projection_kind: str = "portfolio_native"
    interpretation: str = (
        "diagnostic comparison only; does not change selection, ranking, "
        "actionability, scoring, or live behavior"
    )

    @property
    def matches(self) -> bool:
        """Return whether all compared fields are equal."""

        return not self.differences


_EXPECTED_COMPATIBILITY_FIELDS = frozenset(
    {
        "actionability_state",
        "confidence",
        "rank",
        "ranking_score",
    }
)


@dataclass(frozen=True, slots=True)
class NamedAnalysisComparison:
    """Associate one deterministic fixture identity with its report."""

    fixture_id: str
    report: AnalysisComparisonReport

    def __post_init__(self) -> None:
        if not self.fixture_id.strip():
            raise ValueError("comparison fixture identity cannot be empty")


@dataclass(frozen=True, slots=True)
class AnalysisComparisonSummary:
    """Aggregate non-authoritative rollout comparison diagnostics."""

    total_count: int
    match_count: int
    difference_count: int
    compatibility_only_count: int
    regression_count: int
    field_difference_counts: dict[str, int]
    regression_field_counts: dict[str, int]
    compatibility_fixture_ids: tuple[str, ...]
    regression_fixture_ids: tuple[str, ...]
    interpretation: str = (
        "diagnostic summary only; expected compatibility gaps are separated "
        "from structural output regressions"
    )


def summarize_analysis_comparisons(
    comparisons: Sequence[NamedAnalysisComparison],
) -> AnalysisComparisonSummary:
    """Aggregate deterministic fixture comparisons without changing behavior."""

    field_counts: Counter[str] = Counter()
    regression_counts: Counter[str] = Counter()
    compatibility_fixture_ids: list[str] = []
    regression_fixture_ids: list[str] = []
    match_count = 0

    for comparison in comparisons:
        differences = comparison.report.differences
        if not differences:
            match_count += 1
            continue

        fields = {difference.field for difference in differences}
        field_counts.update(fields)
        regression_fields = fields - _EXPECTED_COMPATIBILITY_FIELDS
        if regression_fields:
            regression_fixture_ids.append(comparison.fixture_id)
            regression_counts.update(regression_fields)
        else:
            compatibility_fixture_ids.append(comparison.fixture_id)

    total_count = len(comparisons)
    return AnalysisComparisonSummary(
        total_count=total_count,
        match_count=match_count,
        difference_count=total_count - match_count,
        compatibility_only_count=len(compatibility_fixture_ids),
        regression_count=len(regression_fixture_ids),
        field_difference_counts=dict(sorted(field_counts.items())),
        regression_field_counts=dict(sorted(regression_counts.items())),
        compatibility_fixture_ids=tuple(compatibility_fixture_ids),
        regression_fixture_ids=tuple(regression_fixture_ids),
    )


def comparison_summary_payload(
    summary: AnalysisComparisonSummary,
) -> dict[str, Any]:
    """Serialize a deterministic, explicitly non-authoritative summary."""

    return {
        "total_count": summary.total_count,
        "match_count": summary.match_count,
        "difference_count": summary.difference_count,
        "compatibility_only_count": summary.compatibility_only_count,
        "regression_count": summary.regression_count,
        "field_difference_counts": summary.field_difference_counts,
        "regression_field_counts": summary.regression_field_counts,
        "compatibility_fixture_ids": list(summary.compatibility_fixture_ids),
        "regression_fixture_ids": list(summary.regression_fixture_ids),
        "authoritative": False,
        "interpretation": summary.interpretation,
    }


def compare_analysis_outputs(
    legacy_payload: Mapping[str, Any],
    new_payload: Mapping[str, Any],
    *,
    legacy_projection_kind: str = "legacy_single_winner",
    new_projection_kind: str = "portfolio_native",
) -> AnalysisComparisonReport:
    """Compare two explicitly distinct legacy and portfolio projections."""

    if legacy_payload is new_payload:
        raise ValueError("rollout comparison requires distinct projection payload objects")
    if not legacy_projection_kind.strip() or not new_projection_kind.strip():
        raise ValueError("rollout projection kinds cannot be empty")
    if legacy_projection_kind == new_projection_kind:
        raise ValueError("rollout comparison requires distinct projection kinds")

    legacy = _legacy_projection(legacy_payload)
    new = _new_projection(new_payload)

    fields = (
        "opportunity_count",
        "selected_strategy",
        "direction",
        "entry_zone",
        "stop",
        "targets",
        "actionability_state",
        "rejection_reasons",
        "confidence",
        "rank",
        "ranking_score",
    )
    differences = tuple(
        DiagnosticDifference(field, legacy[field], new[field])
        for field in fields
        if legacy[field] != new[field]
    )

    symbol = _string_or_none(new_payload.get("symbol"))
    if symbol is None:
        symbol = _string_or_none(legacy_payload.get("symbol"))

    return AnalysisComparisonReport(
        symbol=symbol,
        legacy_opportunity_count=int(legacy["opportunity_count"]),
        new_opportunity_count=int(new["opportunity_count"]),
        differences=differences,
        legacy_projection_kind=legacy_projection_kind,
        new_projection_kind=new_projection_kind,
    )


def analysis_comparison_payload(report: AnalysisComparisonReport) -> dict[str, Any]:
    """Serialize a comparison report into a stable diagnostic payload."""

    return {
        "symbol": report.symbol,
        "matches": report.matches,
        "legacy_opportunity_count": report.legacy_opportunity_count,
        "new_opportunity_count": report.new_opportunity_count,
        "legacy_projection_kind": report.legacy_projection_kind,
        "new_projection_kind": report.new_projection_kind,
        "distinct_projection_sources": True,
        "differences": [
            {
                "field": difference.field,
                "legacy": difference.legacy,
                "new": difference.new,
            }
            for difference in report.differences
        ],
        "authoritative": False,
        "interpretation": report.interpretation,
    }


def _legacy_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    setup = _mapping(payload.get("setup"))
    if setup is None:
        setup = _mapping(payload.get("developing_setup"))

    candidate_count = 1 if setup is not None else 0
    reasons = _normalized_strings(payload.get("reasons", payload.get("rejection_reasons", ())))

    return {
        "opportunity_count": candidate_count,
        "selected_strategy": _lookup(setup, "strategy"),
        "direction": _lookup(setup, "direction"),
        "entry_zone": _entry_zone(setup),
        "stop": _stop(setup),
        "targets": _targets(setup),
        "actionability_state": (
            payload.get("entry_state")
            if payload.get("entry_state") is not None
            else _lookup(setup, "entry_status")
        ),
        "rejection_reasons": reasons,
        "confidence": (
            payload.get("confidence_score")
            if payload.get("confidence_score") is not None
            else _lookup(setup, "confidence_score")
        ),
        "rank": payload.get("rank"),
        "ranking_score": _first_present(
            payload,
            ("final_rank_score", "ranking_score", "quality_score"),
        ),
    }


def _new_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    portfolio = _mapping(payload.get("opportunity_portfolio"))
    if portfolio is None:
        portfolio = payload

    opportunities = _portfolio_opportunities(portfolio)
    primary = _primary_opportunity(portfolio, opportunities)

    reasons = _normalized_strings(
        payload.get(
            "rejection_reasons",
            payload.get("reasons", portfolio.get("rejection_reasons", ())),
        )
    )

    actionability = None
    if primary is not None:
        actionability_payload = _mapping(primary.get("actionability_state"))
        if actionability_payload is not None:
            actionability = actionability_payload.get("state")
        if actionability is None:
            actionability = primary.get("entry_status")
    if actionability is None:
        actionability = portfolio.get("public_decision")

    return {
        "opportunity_count": int(portfolio.get("opportunity_count", len(opportunities))),
        "selected_strategy": _lookup(primary, "strategy"),
        "direction": _lookup(primary, "direction"),
        "entry_zone": _entry_zone(primary),
        "stop": _stop(primary),
        "targets": _targets(primary),
        "actionability_state": actionability,
        "rejection_reasons": reasons,
        "confidence": _first_present(
            primary,
            ("confidence", "confidence_score", "quality_score"),
        ),
        "rank": _first_present(primary, ("rank", "candidate_rank")),
        "ranking_score": _first_present(
            primary,
            ("final_rank_score", "ranking_score", "quality_score"),
        ),
    }


def _portfolio_opportunities(
    portfolio: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    collected: list[Mapping[str, Any]] = []
    for key in _PORTFOLIO_SLOT_KEYS:
        item = _mapping(portfolio.get(key))
        if item is not None:
            collected.append(item)

    follow_ups = portfolio.get("follow_up_opportunities", ())
    if isinstance(follow_ups, Sequence) and not isinstance(follow_ups, str | bytes):
        collected.extend(item for value in follow_ups if (item := _mapping(value)) is not None)

    explicit = portfolio.get("opportunities")
    if not collected and isinstance(explicit, Sequence) and not isinstance(explicit, str | bytes):
        collected.extend(item for value in explicit if (item := _mapping(value)) is not None)
    return tuple(collected)


def _primary_opportunity(
    portfolio: Mapping[str, Any],
    opportunities: tuple[Mapping[str, Any], ...],
) -> Mapping[str, Any] | None:
    primary_id = portfolio.get("primary_opportunity_id")
    if primary_id is not None:
        for opportunity in opportunities:
            if opportunity.get("opportunity_id") == primary_id:
                return opportunity
    return opportunities[0] if opportunities else None


def _entry_zone(value: Mapping[str, Any] | None) -> Any:
    if value is None:
        return None
    zone = _mapping(value.get("entry_zone"))
    if zone is None:
        zone = _mapping(value.get("entry"))
    if zone is None:
        return None
    normalized = {key: zone.get(key) for key in ("lower", "upper", "preferred") if key in zone}
    maximum_chase = (
        zone.get("maximum_chase") if "maximum_chase" in zone else zone.get("maximum_chase_price")
    )
    if maximum_chase is not None:
        normalized["maximum_chase"] = maximum_chase
    return normalized


def _stop(value: Mapping[str, Any] | None) -> Any:
    if value is None:
        return None
    stop = value.get("stop")
    if isinstance(stop, Mapping):
        return stop.get("price")
    if stop is not None:
        return stop
    stop_loss = _mapping(value.get("stop_loss"))
    return None if stop_loss is None else stop_loss.get("price")


def _targets(value: Mapping[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    raw = value.get("targets", value.get("take_profits", ()))
    if not isinstance(raw, Sequence) or isinstance(raw, str | bytes):
        return ()
    normalized: list[dict[str, Any]] = []
    for target in raw:
        mapping = _mapping(target)
        if mapping is None:
            continue
        normalized.append(
            {key: mapping.get(key) for key in ("label", "price", "risk_reward") if key in mapping}
        )
    return tuple(normalized)


def _lookup(value: Mapping[str, Any] | None, key: str) -> Any:
    return None if value is None else value.get(key)


def _first_present(
    value: Mapping[str, Any] | None,
    keys: tuple[str, ...],
) -> Any:
    if value is None:
        return None
    for key in keys:
        candidate = value.get(key, _MISSING)
        if candidate is not _MISSING and candidate is not None:
            return candidate
    return None


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _normalized_strings(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return tuple(str(item) for item in value)
    return ()


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


__all__ = [
    "AnalysisComparisonReport",
    "AnalysisComparisonSummary",
    "DiagnosticDifference",
    "NamedAnalysisComparison",
    "analysis_comparison_payload",
    "compare_analysis_outputs",
    "comparison_summary_payload",
    "summarize_analysis_comparisons",
]
