"""Deterministic ranking for scored strategy candidates."""

from __future__ import annotations

from apex.scoring.contracts import CandidateOutcome, RankedCandidate, ScoredCandidate
from apex.scoring.rank_score import final_rank_score
from apex.strategies.contracts import StrategyType, TradeDirection

_DIRECTION_ORDER: dict[TradeDirection, int] = {
    TradeDirection.LONG: 0,
    TradeDirection.SHORT: 1,
}


def _sort_key(
    item: ScoredCandidate,
    strategy_order: tuple[StrategyType, ...],
) -> tuple[float, float, float, float, float, int, int, str]:
    quality = item.candidate.quality
    return (
        -final_rank_score(item),
        -quality.target_space_quality,
        -quality.entry_quality,
        quality.conflict_penalty,
        quality.extension_penalty,
        strategy_order.index(item.candidate.strategy),
        _DIRECTION_ORDER[item.candidate.direction],
        item.candidate_id,
    )


def rank_candidates(
    scored: tuple[ScoredCandidate, ...],
    *,
    strategy_order: tuple[StrategyType, ...],
) -> tuple[RankedCandidate, ...]:
    """Return stable ranked candidates independent of input ordering."""

    ordered = sorted(scored, key=lambda item: _sort_key(item, strategy_order))
    ranked: list[RankedCandidate] = []
    for rank, item in enumerate(ordered, start=1):
        quality = item.candidate.quality
        ranked.append(
            RankedCandidate(
                scored=item,
                rank=rank,
                outcome=CandidateOutcome.DOWNGRADED,
                reasons=(),
                tie_break=(
                    f"final_rank_score={final_rank_score(item):.6f}",
                    f"legacy_final_score={item.final_score:.6f}",
                    f"target_space_quality={quality.target_space_quality:.6f}",
                    f"entry_quality={quality.entry_quality:.6f}",
                    f"conflict_penalty={quality.conflict_penalty:.6f}",
                    f"extension_penalty={quality.extension_penalty:.6f}",
                    f"strategy_order={strategy_order.index(item.candidate.strategy)}",
                    f"direction_order={_DIRECTION_ORDER[item.candidate.direction]}",
                ),
            )
        )
    return tuple(ranked)
