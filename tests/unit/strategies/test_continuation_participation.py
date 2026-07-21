from datetime import UTC, datetime, timedelta

from apex.domain.futures_evidence import (
    MarketEvidenceBundle,
    OpenInterestSnapshot,
    TakerFlowSnapshot,
)
from apex.strategies.context import FeatureSnapshot
from apex.strategies.continuation_participation import (
    ParticipationState,
    assess_continuation_participation,
)
from apex.strategies.contracts import TradeDirection

NOW = datetime(2026, 7, 21, tzinfo=UTC)


def test_missing_participation_inputs_remain_unavailable_not_negative() -> None:
    result = assess_continuation_participation(
        direction=TradeDirection.LONG,
        features=FeatureSnapshot(atr=2.0),
        market_evidence=None,
    )

    assert result.state is ParticipationState.UNAVAILABLE
    assert result.available_signal_count == 0
    assert result.supportive_signal_count == 0
    assert result.contradictory_signal_count == 0


def test_relative_volume_can_support_without_open_interest() -> None:
    result = assess_continuation_participation(
        direction=TradeDirection.LONG,
        features=FeatureSnapshot(atr=2.0, relative_volume=1.5),
        market_evidence=None,
    )

    assert result.state is ParticipationState.SUPPORTIVE
    assert result.available_signal_count == 1
    assert result.open_interest_change is None


def test_rising_open_interest_and_long_taker_flow_support_long() -> None:
    evidence = MarketEvidenceBundle(
        symbol="TESTUSDT",
        as_of=NOW,
        open_interest=(
            OpenInterestSnapshot(
                symbol="TESTUSDT",
                period="5m",
                open_interest=100.0,
                open_interest_value=1000.0,
                captured_at=NOW - timedelta(minutes=5),
                source="test",
            ),
            OpenInterestSnapshot(
                symbol="TESTUSDT",
                period="5m",
                open_interest=103.0,
                open_interest_value=1030.0,
                captured_at=NOW,
                source="test",
            ),
        ),
        taker_flow=(
            TakerFlowSnapshot(
                symbol="TESTUSDT",
                period="5m",
                buy_volume=110.0,
                sell_volume=90.0,
                buy_sell_ratio=1.22,
                captured_at=NOW,
                source="test",
            ),
        ),
        source="test",
    )

    result = assess_continuation_participation(
        direction=TradeDirection.LONG,
        features=FeatureSnapshot(atr=2.0, relative_volume=1.3),
        market_evidence=evidence,
    )

    assert result.state is ParticipationState.SUPPORTIVE
    assert result.supportive_signal_count == 3
    assert result.open_interest_change == 0.03


def test_taker_flow_is_directionally_symmetric_for_short() -> None:
    evidence = MarketEvidenceBundle(
        symbol="TESTUSDT",
        as_of=NOW,
        taker_flow=(
            TakerFlowSnapshot(
                symbol="TESTUSDT",
                period="5m",
                buy_volume=80.0,
                sell_volume=120.0,
                buy_sell_ratio=0.67,
                captured_at=NOW,
                source="test",
            ),
        ),
        source="test",
    )

    result = assess_continuation_participation(
        direction=TradeDirection.SHORT,
        features=FeatureSnapshot(atr=2.0),
        market_evidence=evidence,
    )

    assert result.state is ParticipationState.SUPPORTIVE
    assert result.supportive_signal_count == 1


def test_contracting_open_interest_and_opposed_flow_are_contradictory() -> None:
    evidence = MarketEvidenceBundle(
        symbol="TESTUSDT",
        as_of=NOW,
        open_interest=(
            OpenInterestSnapshot(
                symbol="TESTUSDT",
                period="5m",
                open_interest=100.0,
                open_interest_value=1000.0,
                captured_at=NOW - timedelta(minutes=5),
                source="test",
            ),
            OpenInterestSnapshot(
                symbol="TESTUSDT",
                period="5m",
                open_interest=95.0,
                open_interest_value=950.0,
                captured_at=NOW,
                source="test",
            ),
        ),
        taker_flow=(
            TakerFlowSnapshot(
                symbol="TESTUSDT",
                period="5m",
                buy_volume=80.0,
                sell_volume=120.0,
                buy_sell_ratio=0.67,
                captured_at=NOW,
                source="test",
            ),
        ),
        source="test",
    )

    result = assess_continuation_participation(
        direction=TradeDirection.LONG,
        features=FeatureSnapshot(atr=2.0, relative_volume=0.7),
        market_evidence=evidence,
    )

    assert result.state is ParticipationState.CONTRADICTORY
    assert result.contradictory_signal_count == 3
