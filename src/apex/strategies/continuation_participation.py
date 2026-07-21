"""Optional continuation participation evidence with neutral missing-data semantics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.domain.futures_evidence import MarketEvidenceBundle
from apex.strategies.context import FeatureSnapshot
from apex.strategies.contracts import TradeDirection


class ParticipationState(StrEnum):
    """Directional participation state for continuation analysis."""

    UNAVAILABLE = "unavailable"
    NEUTRAL = "neutral"
    SUPPORTIVE = "supportive"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class ContinuationParticipation:
    """Optional volume/OI/taker evidence without fabricated defaults."""

    state: ParticipationState
    relative_volume: float | None
    open_interest_change: float | None
    taker_buy_sell_ratio: float | None
    available_signal_count: int
    supportive_signal_count: int
    contradictory_signal_count: int
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.available_signal_count < 0:
            raise ValueError("available signal count cannot be negative")
        if self.supportive_signal_count < 0 or self.contradictory_signal_count < 0:
            raise ValueError("participation signal counts cannot be negative")
        if (
            self.supportive_signal_count + self.contradictory_signal_count
            > self.available_signal_count
        ):
            raise ValueError("classified participation signals exceed available signals")
        if not self.reasons:
            raise ValueError("participation evidence requires explanatory reasons")


def assess_continuation_participation(
    *,
    direction: TradeDirection,
    features: FeatureSnapshot,
    market_evidence: MarketEvidenceBundle | None,
) -> ContinuationParticipation:
    """Assess optional participation evidence; unavailable data stays neutral."""

    relative_volume = features.relative_volume
    open_interest_change = _open_interest_change(market_evidence)
    taker_ratio = _latest_taker_ratio(market_evidence)

    observations: list[tuple[bool | None, str]] = []

    if relative_volume is None:
        observations.append((None, "relative-volume evidence is unavailable"))
    elif relative_volume >= 1.20:
        observations.append((True, "relative volume supports continuation"))
    elif relative_volume < 0.80:
        observations.append((False, "relative volume is weak for continuation"))
    else:
        observations.append((None, "relative volume is neutral"))

    if open_interest_change is None:
        observations.append((None, "open-interest change is unavailable"))
    elif open_interest_change >= 0.02:
        observations.append((True, "open interest expanded with the move"))
    elif open_interest_change <= -0.02:
        observations.append((False, "open interest contracted during the move"))
    else:
        observations.append((None, "open-interest change is neutral"))

    if taker_ratio is None:
        observations.append((None, "taker-flow evidence is unavailable"))
    else:
        supportive = (
            taker_ratio >= 1.05 if direction is TradeDirection.LONG else taker_ratio <= 0.95
        )
        contradictory = (
            taker_ratio <= 0.95 if direction is TradeDirection.LONG else taker_ratio >= 1.05
        )
        if supportive:
            observations.append((True, "taker flow supports the continuation direction"))
        elif contradictory:
            observations.append((False, "taker flow opposes the continuation direction"))
        else:
            observations.append((None, "taker flow is neutral"))

    available = sum(
        value is not None for value in (relative_volume, open_interest_change, taker_ratio)
    )
    supportive_count = sum(result is True for result, _ in observations)
    contradictory_count = sum(result is False for result, _ in observations)

    if available == 0:
        state = ParticipationState.UNAVAILABLE
    elif contradictory_count > supportive_count:
        state = ParticipationState.CONTRADICTORY
    elif supportive_count > contradictory_count:
        state = ParticipationState.SUPPORTIVE
    else:
        state = ParticipationState.NEUTRAL

    return ContinuationParticipation(
        state=state,
        relative_volume=relative_volume,
        open_interest_change=open_interest_change,
        taker_buy_sell_ratio=taker_ratio,
        available_signal_count=available,
        supportive_signal_count=supportive_count,
        contradictory_signal_count=contradictory_count,
        reasons=tuple(reason for _, reason in observations),
    )


def _open_interest_change(
    market_evidence: MarketEvidenceBundle | None,
) -> float | None:
    if market_evidence is None or len(market_evidence.open_interest) < 2:
        return None
    previous, latest = market_evidence.open_interest[-2:]
    if previous.open_interest_value <= 0:
        return None
    return (
        latest.open_interest_value - previous.open_interest_value
    ) / previous.open_interest_value


def _latest_taker_ratio(
    market_evidence: MarketEvidenceBundle | None,
) -> float | None:
    if market_evidence is None or not market_evidence.taker_flow:
        return None
    return market_evidence.taker_flow[-1].buy_sell_ratio


__all__ = [
    "ContinuationParticipation",
    "ParticipationState",
    "assess_continuation_participation",
]
