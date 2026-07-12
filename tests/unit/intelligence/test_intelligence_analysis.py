from datetime import UTC, datetime, timedelta

import pytest

from apex.config import FileSettings
from apex.domain import Candle
from apex.intelligence import (
    FundingRateSnapshot,
    OpenInterestSnapshot,
    calculate_symbol_correlation,
    disabled_intelligence_metadata,
    intelligence_metadata,
    summarize_market_risk,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _candles(symbol: str, closes: tuple[float, ...]) -> tuple[Candle, ...]:
    return tuple(
        Candle(
            symbol=symbol,
            timeframe="5m",
            open_time=NOW + timedelta(minutes=index),
            close_time=NOW + timedelta(minutes=index + 1),
            open=close,
            high=close + 1.0,
            low=close - 1.0,
            close=close,
            volume=100.0,
            is_closed=True,
            source="fixture",
        )
        for index, close in enumerate(closes)
    )


def test_intelligence_flags_are_disabled_by_default() -> None:
    settings = FileSettings()

    assert settings.advanced_intelligence_enabled is False
    assert settings.intelligence_funding_enabled is False
    assert settings.intelligence_open_interest_enabled is False
    assert settings.intelligence_correlation_enabled is False
    assert disabled_intelligence_metadata() == {"enabled": False, "warnings": []}


def test_symbol_correlation_is_deterministic() -> None:
    correlation = calculate_symbol_correlation(
        "BTC/USDT",
        "ETH/USDT",
        _candles("BTC/USDT", (100.0, 101.0, 102.0, 103.0)),
        _candles("ETH/USDT", (50.0, 51.0, 52.0, 53.0)),
    )

    assert correlation.sample_size == 3
    assert correlation.correlation == pytest.approx(1.0, abs=0.02)


def test_market_risk_summary_is_metadata_only() -> None:
    summary = summarize_market_risk(
        funding=(
            FundingRateSnapshot(
                symbol="BTC/USDT",
                funding_rate=0.002,
                captured_at=NOW,
                source="fixture",
            ),
        ),
        open_interest=(
            OpenInterestSnapshot(
                symbol="BTC/USDT",
                open_interest=1000.0,
                captured_at=NOW,
                source="fixture",
            ),
        ),
    )
    metadata = intelligence_metadata(summary)

    assert summary.risk_score == pytest.approx(0.4)
    assert metadata["funding_count"] == 1
    assert "elevated funding pressure" in metadata["warnings"]
