from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from apex.strategies import (
    CandidateLifecycle,
    CandidateLifecycleStatus,
    EntryMode,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyEvidence,
    StrategyType,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _entry() -> EntryZone:
    return EntryZone(
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        current_price=100.0,
        distance_from_current=0.0,
        atr_distance=0.0,
        estimated_move_missed=0.0,
        location_quality=1.0,
        mode=EntryMode.MARKET_NEAR,
        rationale=("current price is valid",),
    )


def _quality() -> RawQualityMetrics:
    return RawQualityMetrics(
        trend_alignment=0.5,
        structure_quality=0.5,
        entry_quality=0.5,
        momentum_quality=0.5,
        volume_quality=0.5,
        liquidity_quality=0.5,
        target_space_quality=0.5,
    )


def _candidate(
    *,
    direction: TradeDirection = TradeDirection.LONG,
    decision_time: datetime = NOW,
    metadata: dict[str, str | int | float | bool] | None = None,
) -> TradeCandidate:
    return TradeCandidate(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=direction,
        decision_time=decision_time,
        entry=_entry(),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=98.0 if direction is TradeDirection.LONG else 102.0,
            rationale=("structure fails",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=103.0 if direction is TradeDirection.LONG else 97.0,
                    label="primary",
                    rationale=("opposing structure",),
                ),
            )
        ),
        quality=_quality(),
        evidence=StrategyEvidence(supporting=("valid thesis",)),
        metadata={} if metadata is None else metadata,
    )


@pytest.mark.parametrize("value", [0.0, -1.0, float("nan"), float("inf")])
def test_entry_rejects_invalid_prices(value: float) -> None:
    with pytest.raises(ValueError):
        EntryZone(
            lower=value,
            upper=101.0,
            preferred=100.0,
            current_price=100.0,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=1.0,
            mode=EntryMode.MARKET_NEAR,
            rationale=("invalid",),
        )


def test_candidate_rejects_timezone_naive_decision_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _candidate(decision_time=datetime(2026, 7, 13))


def test_candidate_rejects_invalid_long_geometry() -> None:
    with pytest.raises(ValueError, match="long invalidation"):
        TradeCandidate(
            symbol="BTC/USDT",
            strategy=StrategyType.TREND_PULLBACK,
            direction=TradeDirection.LONG,
            decision_time=NOW,
            entry=_entry(),
            invalidation=InvalidationConcept(
                kind=InvalidationType.STRUCTURAL,
                price=99.0,
                rationale=("invalid",),
            ),
            targets=TargetConcept(
                levels=(
                    TargetLevel(
                        kind=TargetType.STRUCTURAL,
                        price=103.0,
                        label="primary",
                        rationale=("target",),
                    ),
                )
            ),
            quality=_quality(),
            evidence=StrategyEvidence(supporting=("evidence",)),
            metadata={},
        )


def test_candidate_rejects_invalid_short_geometry() -> None:
    with pytest.raises(ValueError, match="short invalidation"):
        TradeCandidate(
            symbol="BTC/USDT",
            strategy=StrategyType.TREND_PULLBACK,
            direction=TradeDirection.SHORT,
            decision_time=NOW,
            entry=_entry(),
            invalidation=InvalidationConcept(
                kind=InvalidationType.STRUCTURAL,
                price=101.0,
                rationale=("invalid",),
            ),
            targets=TargetConcept(
                levels=(
                    TargetLevel(
                        kind=TargetType.STRUCTURAL,
                        price=97.0,
                        label="primary",
                        rationale=("target",),
                    ),
                )
            ),
            quality=_quality(),
            evidence=StrategyEvidence(supporting=("evidence",)),
            metadata={},
        )


def test_target_labels_must_be_unique() -> None:
    level = TargetLevel(
        kind=TargetType.STRUCTURAL,
        price=103.0,
        label="primary",
        rationale=("target",),
    )
    with pytest.raises(ValueError, match="unique"):
        TargetConcept(levels=(level, level))


def test_evidence_references_must_be_unique() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        StrategyEvidence(
            supporting=("valid",),
            feature_references=("rsi", "rsi"),
        )


def test_candidate_metadata_is_immutable_and_copied() -> None:
    source: dict[str, str | int | float | bool] = {"timeframe": "5m"}
    candidate = _candidate(metadata=source)
    source["timeframe"] = "1m"

    assert isinstance(candidate.metadata, MappingProxyType)
    assert candidate.metadata["timeframe"] == "5m"
    with pytest.raises(TypeError):
        candidate.metadata["timeframe"] = "15m"  # type: ignore[index]


def test_candidate_lifecycle_defaults_from_trade_geometry() -> None:
    candidate = _candidate()

    assert candidate.lifecycle is not None
    assert candidate.lifecycle.status is CandidateLifecycleStatus.ACTIVE
    assert candidate.lifecycle.cooldown_key == "BTC/USDT:trend_pullback:long:100.0"
    assert candidate.lifecycle.expires_after_seconds == 1800
    assert candidate.lifecycle.invalidation_price == pytest.approx(98.0)


def test_invalidated_lifecycle_requires_reason() -> None:
    with pytest.raises(ValueError, match="invalidation reason"):
        CandidateLifecycle(
            status=CandidateLifecycleStatus.INVALIDATED,
            invalidation_price=98.0,
            invalidation_reason="",
        )


def test_repeated_candidate_construction_is_deterministic() -> None:
    assert _candidate() == _candidate()
