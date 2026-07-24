"""Hierarchical parent-thesis authority for multi-timeframe discovery."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType

from apex.strategies.analysis import (
    CandidateActionability,
    StrategyAnalysisResult,
    SuppressedStrategyCandidate,
)
from apex.strategies.context import StrategyContext, TimeframeContext, TimeframeRole
from apex.strategies.contracts import TradeCandidate, TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.structure.contracts import TrendDirection


class ParentThesisState(StrEnum):
    ESTABLISHED = "established"
    DEVELOPING = "developing"
    CONFLICT = "conflict"
    NEUTRAL = "neutral"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class ParentTimeframeThesis:
    state: ParentThesisState
    direction: TradeDirection | None
    parent_timeframes: tuple[str, ...]
    supportive_timeframes: tuple[str, ...]
    opposing_timeframes: tuple[str, ...]
    neutral_timeframes: tuple[str, ...]
    execution_timeframe: str | None
    score: float
    reasons: tuple[str, ...]

    @property
    def enforces_direction(self) -> bool:
        return self.state is ParentThesisState.ESTABLISHED and self.direction is not None


@dataclass(frozen=True, slots=True)
class HierarchicalRoutingResult:
    analysis: StrategyAnalysisResult
    thesis: ParentTimeframeThesis
    input_candidate_count: int
    retained_candidate_count: int
    suppressed_candidate_count: int


_BULLISH_VOTES = {
    TrendDirection.STRONG_BULLISH: 2.0,
    TrendDirection.BULLISH: 1.0,
    TrendDirection.WEAK_BULLISH: 0.5,
}
_BEARISH_VOTES = {
    TrendDirection.STRONG_BEARISH: -2.0,
    TrendDirection.BEARISH: -1.0,
    TrendDirection.WEAK_BEARISH: -0.5,
}
_PARENT_ROLES = {TimeframeRole.INTRADAY, TimeframeRole.SETUP}


def derive_parent_timeframe_thesis(context: StrategyContext) -> ParentTimeframeThesis:
    return derive_parent_timeframe_thesis_from_frames(context.frames)


def derive_parent_timeframe_thesis_from_frames(
    frames: Iterable[TimeframeContext],
) -> ParentTimeframeThesis:
    ordered = tuple(frames)
    parents = tuple(frame for frame in ordered if frame.role in _PARENT_ROLES)
    entry = next((frame for frame in ordered if frame.role is TimeframeRole.ENTRY), None)

    if not parents:
        return ParentTimeframeThesis(
            state=ParentThesisState.INSUFFICIENT_DATA,
            direction=None,
            parent_timeframes=(),
            supportive_timeframes=(),
            opposing_timeframes=(),
            neutral_timeframes=(),
            execution_timeframe=None if entry is None else entry.timeframe,
            score=0.0,
            reasons=("no intraday/setup parent timeframe is available",),
        )

    votes = tuple((frame, _trend_vote(frame.structure.trend.direction)) for frame in parents)
    positive = tuple(frame.timeframe for frame, vote in votes if vote > 0.0)
    negative = tuple(frame.timeframe for frame, vote in votes if vote < 0.0)
    neutral = tuple(frame.timeframe for frame, vote in votes if vote == 0.0)
    score = sum(vote for _frame, vote in votes)

    if positive and negative:
        return ParentTimeframeThesis(
            state=ParentThesisState.CONFLICT,
            direction=None,
            parent_timeframes=tuple(frame.timeframe for frame in parents),
            supportive_timeframes=(),
            opposing_timeframes=tuple((*positive, *negative)),
            neutral_timeframes=neutral,
            execution_timeframe=None if entry is None else entry.timeframe,
            score=score,
            reasons=("setup and intraday parent timeframes disagree on direction",),
        )

    if positive:
        direction = TradeDirection.LONG
        directional = positive
    elif negative:
        direction = TradeDirection.SHORT
        directional = negative
    else:
        return ParentTimeframeThesis(
            state=ParentThesisState.NEUTRAL,
            direction=None,
            parent_timeframes=tuple(frame.timeframe for frame in parents),
            supportive_timeframes=(),
            opposing_timeframes=(),
            neutral_timeframes=neutral,
            execution_timeframe=None if entry is None else entry.timeframe,
            score=score,
            reasons=("parent timeframes do not establish a directional thesis",),
        )

    established = len(directional) >= 2 and not neutral
    state = ParentThesisState.ESTABLISHED if established else ParentThesisState.DEVELOPING
    reason = (
        "intraday and setup parent timeframes agree; lower timeframe must search "
        "for execution in the parent direction"
        if established
        else "one parent timeframe is directional while another remains neutral"
    )
    return ParentTimeframeThesis(
        state=state,
        direction=direction,
        parent_timeframes=tuple(frame.timeframe for frame in parents),
        supportive_timeframes=directional,
        opposing_timeframes=(),
        neutral_timeframes=neutral,
        execution_timeframe=None if entry is None else entry.timeframe,
        score=score,
        reasons=(reason,),
    )


def apply_hierarchical_timeframe_routing(
    analysis: StrategyAnalysisResult,
    *,
    context: StrategyContext,
) -> HierarchicalRoutingResult:
    thesis = derive_parent_timeframe_thesis(context)
    retained: list[TradeCandidate] = []
    retained_actionability: list[CandidateActionability] = []
    newly_suppressed: list[SuppressedStrategyCandidate] = []
    geometry_representative_index: dict[tuple[object, ...], int] = {}
    status_by_object = {
        id(item.candidate): item.status for item in analysis.candidate_actionability
    }

    for candidate in analysis.candidates:
        entry_status = status_by_object[id(candidate)]
        enriched = _attach_thesis_metadata(
            candidate,
            thesis,
            entry_status=entry_status,
        )
        if (
            thesis.enforces_direction
            and thesis.direction is not None
            and enriched.direction is not thesis.direction
            and not _has_confirmed_reversal_override(enriched)
        ):
            newly_suppressed.append(
                SuppressedStrategyCandidate(
                    candidate=enriched,
                    reason_codes=("PARENT_THESIS_DIRECTION_CONFLICT",),
                    reasons=(
                        "candidate direction conflicts with the established "
                        "intraday/setup parent thesis",
                    ),
                    entry_status=entry_status,
                    suppression_stage="hierarchical_timeframe_routing",
                )
            )
            continue
        geometry_key = _candidate_geometry_key(enriched)
        representative_index = geometry_representative_index.get(geometry_key)
        if representative_index is not None:
            representative = retained[representative_index]
            aliases = _strategy_aliases(representative)
            aliases.add(enriched.strategy.value)
            representative_metadata = dict(representative.metadata)
            representative_metadata["strategy_aliases"] = ",".join(sorted(aliases))
            representative_metadata["duplicate_geometry_count"] = (
                int(representative_metadata.get("duplicate_geometry_count", 0)) + 1
            )
            representative = replace(
                representative,
                metadata=MappingProxyType(representative_metadata),
            )
            retained[representative_index] = representative
            retained_actionability[representative_index] = CandidateActionability(
                candidate=representative,
                status=retained_actionability[representative_index].status,
            )
            newly_suppressed.append(
                SuppressedStrategyCandidate(
                    candidate=enriched,
                    reason_codes=("DUPLICATE_GEOMETRY_ALIAS",),
                    reasons=(
                        "candidate duplicates an already retained geometry; "
                        "strategy lineage was preserved as an alias",
                    ),
                    entry_status=entry_status,
                    suppression_stage="hierarchical_geometry_deduplication",
                )
            )
            continue

        geometry_representative_index[geometry_key] = len(retained)
        retained.append(enriched)
        retained_actionability.append(
            CandidateActionability(
                candidate=enriched,
                status=status_by_object[id(candidate)],
            )
        )

    routed = replace(
        analysis,
        candidates=tuple(retained),
        candidate_actionability=tuple(retained_actionability),
        suppressed_candidates=analysis.suppressed_candidates + tuple(newly_suppressed),
    )
    return HierarchicalRoutingResult(
        analysis=routed,
        thesis=thesis,
        input_candidate_count=len(analysis.candidates),
        retained_candidate_count=len(retained),
        suppressed_candidate_count=len(newly_suppressed),
    )


def hierarchical_routing_payload(result: HierarchicalRoutingResult) -> dict[str, object]:
    thesis = result.thesis
    return {
        "state": thesis.state.value,
        "direction": None if thesis.direction is None else thesis.direction.value,
        "parent_timeframes": list(thesis.parent_timeframes),
        "supportive_timeframes": list(thesis.supportive_timeframes),
        "opposing_timeframes": list(thesis.opposing_timeframes),
        "neutral_timeframes": list(thesis.neutral_timeframes),
        "execution_timeframe": thesis.execution_timeframe,
        "score": thesis.score,
        "reasons": list(thesis.reasons),
        "direction_enforced": thesis.enforces_direction,
        "input_candidate_count": result.input_candidate_count,
        "retained_candidate_count": result.retained_candidate_count,
        "suppressed_candidate_count": result.suppressed_candidate_count,
    }


def child_timeframe_lineage(
    thesis: ParentTimeframeThesis,
) -> dict[str, str]:
    """Return deterministic setup, execution, invalidation, and target ownership."""

    setup_timeframe = thesis.parent_timeframes[-1] if thesis.parent_timeframes else "unavailable"
    extension_timeframe = (
        thesis.parent_timeframes[0] if thesis.parent_timeframes else setup_timeframe
    )
    execution_timeframe = thesis.execution_timeframe or "unavailable"
    return {
        "setup_timeframe": setup_timeframe,
        "execution_timeframe": execution_timeframe,
        "confirmation_timeframe": execution_timeframe,
        "invalidation_timeframe": setup_timeframe,
        "target_timeframe": setup_timeframe,
        "extension_target_timeframe": extension_timeframe,
    }


def _attach_thesis_metadata(
    candidate: TradeCandidate,
    thesis: ParentTimeframeThesis,
    *,
    entry_status: EntryStatus,
) -> TradeCandidate:
    metadata = dict(candidate.metadata)
    same_direction = thesis.direction is not None and candidate.direction is thesis.direction
    metadata.update(child_timeframe_lineage(thesis))
    metadata.update(
        {
            "parent_thesis_state": thesis.state.value,
            "parent_thesis_direction": (
                "none" if thesis.direction is None else thesis.direction.value
            ),
            "parent_thesis_timeframes": ",".join(thesis.parent_timeframes),
            "parent_supportive_timeframes": ",".join(thesis.supportive_timeframes),
            "parent_opposing_timeframes": ",".join(thesis.opposing_timeframes),
            "execution_search_timeframe": thesis.execution_timeframe or "unavailable",
            "hierarchical_child_entry_search": int(same_direction),
            "child_entry_status": entry_status.value,
            "parent_thesis_waiting_for_child_trigger": int(
                same_direction
                and entry_status
                not in {
                    EntryStatus.READY_NOW,
                    EntryStatus.AGGRESSIVE_NOW,
                }
            ),
        }
    )
    return replace(candidate, metadata=MappingProxyType(metadata))


def is_hierarchical_pre_entry_candidate(
    candidate: TradeCandidate,
    *,
    entry_status: EntryStatus,
) -> bool:
    """Return whether a retained child setup is waiting for lower-TF activation."""

    if entry_status in {
        EntryStatus.READY_NOW,
        EntryStatus.AGGRESSIVE_NOW,
        EntryStatus.INVALIDATED,
    }:
        return False
    metadata = candidate.metadata
    return (
        metadata.get("parent_thesis_state") == ParentThesisState.ESTABLISHED.value
        and metadata.get("hierarchical_child_entry_search") == 1
        and metadata.get("parent_thesis_waiting_for_child_trigger") == 1
    )


def _candidate_geometry_key(candidate: TradeCandidate) -> tuple[object, ...]:
    "Return an exact, strategy-independent geometry identity."

    opportunities = tuple(
        (
            round(opportunity.lower, 12),
            round(opportunity.upper, 12),
            round(opportunity.preferred, 12),
            opportunity.mode.value,
        )
        for opportunity in candidate.entry_opportunities
    )
    targets = tuple(
        (
            level.kind.value,
            round(level.price, 12),
            level.label,
        )
        for level in candidate.targets.levels
    )
    return (
        candidate.symbol,
        candidate.direction.value,
        opportunities,
        candidate.invalidation.kind.value,
        round(candidate.invalidation.price, 12),
        targets,
        candidate.metadata.get("parent_thesis_state"),
        candidate.metadata.get("parent_thesis_direction"),
        candidate.metadata.get("setup_timeframe"),
        candidate.metadata.get("execution_timeframe"),
    )


def _strategy_aliases(candidate: TradeCandidate) -> set[str]:
    aliases = {candidate.strategy.value}
    raw_aliases = candidate.metadata.get("strategy_aliases")
    if isinstance(raw_aliases, str):
        aliases.update(alias for alias in raw_aliases.split(",") if alias)
    return aliases


def _has_confirmed_reversal_override(candidate: TradeCandidate) -> bool:
    return candidate.metadata.get("confirmed_reversal_override") is True


def _trend_vote(direction: TrendDirection) -> float:
    if direction in _BULLISH_VOTES:
        return _BULLISH_VOTES[direction]
    if direction in _BEARISH_VOTES:
        return _BEARISH_VOTES[direction]
    return 0.0


__all__ = [
    "HierarchicalRoutingResult",
    "ParentThesisState",
    "ParentTimeframeThesis",
    "apply_hierarchical_timeframe_routing",
    "child_timeframe_lineage",
    "derive_parent_timeframe_thesis",
    "derive_parent_timeframe_thesis_from_frames",
    "hierarchical_routing_payload",
    "is_hierarchical_pre_entry_candidate",
]
