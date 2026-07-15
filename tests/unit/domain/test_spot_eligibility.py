from __future__ import annotations

import pytest

from apex.domain.spot_market import (
    SpotEligibilityReason,
    SpotEligibilityThresholds,
    SpotMarketMetadata,
    evaluate_spot_symbol_eligibility,
)


def _thresholds(**overrides: object) -> SpotEligibilityThresholds:
    values: dict[str, object] = {
        "minimum_quote_volume_24h": 10_000_000.0,
        "minimum_market_age_days": None,
        "maximum_spread_percentage": 0.25,
        "minimum_candle_count": 60,
        "minimum_atr_percentage": 0.15,
        "maximum_downside_volatility_percentage": 4.0,
        "excluded_symbols": (),
    }
    values.update(overrides)
    return SpotEligibilityThresholds.model_validate(values)


def _metadata(**overrides: object) -> SpotMarketMetadata:
    values: dict[str, object] = {
        "symbol": "BTCUSDT",
        "base_asset": "BTC",
        "quote_asset": "USDT",
        "quote_volume_24h": 50_000_000.0,
        "spread_percentage": 0.05,
        "market_age_days": None,
        "available_candle_count": 200,
        "has_data_gaps": False,
        "atr_percentage": 1.2,
        "downside_volatility_percentage": 1.0,
        "terminal_extension": False,
    }
    values.update(overrides)
    return SpotMarketMetadata.model_validate(values)


def test_eligible_symbol() -> None:
    result = evaluate_spot_symbol_eligibility(_metadata(), _thresholds())
    assert result.eligible is True
    assert result.reasons == (SpotEligibilityReason.ELIGIBLE,)


@pytest.mark.parametrize(
    ("metadata_overrides", "threshold_overrides", "reason"),
    [
        ({"quote_volume_24h": 1.0}, {}, SpotEligibilityReason.INSUFFICIENT_QUOTE_VOLUME),
        ({"spread_percentage": 0.5}, {}, SpotEligibilityReason.SPREAD_TOO_WIDE),
        ({"available_candle_count": 59}, {}, SpotEligibilityReason.INSUFFICIENT_CANDLE_HISTORY),
        ({"has_data_gaps": True}, {}, SpotEligibilityReason.DATA_GAPS),
        ({"atr_percentage": 0.01}, {}, SpotEligibilityReason.INSUFFICIENT_ATR),
        (
            {"downside_volatility_percentage": 5.0},
            {},
            SpotEligibilityReason.DOWNSIDE_VOLATILITY_TOO_HIGH,
        ),
        ({"terminal_extension": True}, {}, SpotEligibilityReason.TERMINAL_EXTENSION),
        ({}, {"excluded_symbols": ("BTCUSDT",)}, SpotEligibilityReason.EXCLUDED_SYMBOL),
    ],
)
def test_each_eligibility_rejection(
    metadata_overrides: dict[str, object],
    threshold_overrides: dict[str, object],
    reason: SpotEligibilityReason,
) -> None:
    result = evaluate_spot_symbol_eligibility(
        _metadata(**metadata_overrides),
        _thresholds(**threshold_overrides),
    )
    assert result.eligible is False
    assert reason in result.reasons


def test_unavailable_market_age_is_ignored_when_threshold_is_disabled() -> None:
    result = evaluate_spot_symbol_eligibility(
        _metadata(market_age_days=None),
        _thresholds(minimum_market_age_days=None),
    )
    assert result.eligible is True


def test_unavailable_market_age_rejects_when_threshold_is_required() -> None:
    result = evaluate_spot_symbol_eligibility(
        _metadata(market_age_days=None),
        _thresholds(minimum_market_age_days=30),
    )
    assert result.eligible is False
    assert SpotEligibilityReason.INSUFFICIENT_MARKET_HISTORY in result.reasons
