from __future__ import annotations

import pytest

from apex.application.exposure_classification import classify_proposed_exposure
from apex.strategies import TradeDirection


def test_stable_quote_trade_uses_full_automatic_exposure() -> None:
    result = classify_proposed_exposure(
        symbol="btcusdt",
        direction=TradeDirection.LONG,
        risk_pct=0.75,
    )
    assert result.symbol == "BTC/USDT"
    assert result.direction_bucket == "LONG"
    assert result.correlation_bucket == "CRYPTO_STABLE_QUOTE"
    assert result.directional_exposure_pct == pytest.approx(0.75)
    assert result.correlated_exposure_pct == pytest.approx(0.75)
    assert result.directional_source == "automatic"
    assert result.correlated_source == "automatic"


def test_cross_pair_does_not_fabricate_correlation() -> None:
    result = classify_proposed_exposure(
        symbol="ETH/BTC",
        direction=TradeDirection.SHORT,
        risk_pct=0.5,
    )
    assert result.direction_bucket == "SHORT"
    assert result.correlation_bucket == "CRYPTO_CROSS"
    assert result.directional_exposure_pct == pytest.approx(0.5)
    assert result.correlated_exposure_pct == pytest.approx(0.0)


def test_explicit_overrides_are_preserved() -> None:
    result = classify_proposed_exposure(
        symbol="SOLUSDT",
        direction=TradeDirection.LONG,
        risk_pct=1.0,
        directional_override_pct=0.4,
        correlated_override_pct=0.2,
    )
    assert result.directional_exposure_pct == pytest.approx(0.4)
    assert result.correlated_exposure_pct == pytest.approx(0.2)
    assert result.directional_source == "override"
    assert result.correlated_source == "override"


def test_override_cannot_exceed_trade_risk() -> None:
    with pytest.raises(ValueError, match="cannot exceed proposed risk"):
        classify_proposed_exposure(
            symbol="BTCUSDT",
            direction=TradeDirection.LONG,
            risk_pct=0.5,
            correlated_override_pct=0.6,
        )
