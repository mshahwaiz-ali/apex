from apex.domain import (
    SpotEligibilityReason,
    SpotEligibilityThresholds,
    SpotMarketBreadthSnapshot,
    SpotMarketMetadata,
    SpotRelativeStrengthSnapshot,
    SpotScannerMode,
    evaluate_spot_symbol_eligibility,
)


def _thresholds() -> SpotEligibilityThresholds:
    return SpotEligibilityThresholds(
        minimum_quote_volume_24h=10_000_000,
        minimum_market_age_days=180,
        maximum_spread_percentage=0.25,
        minimum_candle_count=300,
        minimum_atr_percentage=1.0,
        maximum_downside_volatility_percentage=12.0,
        excluded_symbols=("BADUSDT",),
    )


def test_eligible_spot_symbol_returns_single_eligible_reason() -> None:
    result = evaluate_spot_symbol_eligibility(
        SpotMarketMetadata(
            symbol="ETHUSDT",
            base_asset="ETH",
            quote_asset="USDT",
            quote_volume_24h=500_000_000,
            spread_percentage=0.02,
            market_age_days=2_000,
            available_candle_count=1_000,
            atr_percentage=3.5,
            downside_volatility_percentage=5.0,
        ),
        _thresholds(),
    )

    assert result.eligible is True
    assert result.reasons == (SpotEligibilityReason.ELIGIBLE,)


def test_missing_and_unsafe_market_data_is_rejected_deterministically() -> None:
    result = evaluate_spot_symbol_eligibility(
        SpotMarketMetadata(
            symbol="BADUSDT",
            base_asset="BAD",
            quote_asset="USDT",
            quote_volume_24h=1_000,
            available_candle_count=20,
            has_data_gaps=True,
            terminal_extension=True,
        ),
        _thresholds(),
    )

    assert result.eligible is False
    assert SpotEligibilityReason.EXCLUDED_SYMBOL in result.reasons
    assert SpotEligibilityReason.INSUFFICIENT_MARKET_HISTORY in result.reasons
    assert SpotEligibilityReason.SPREAD_TOO_WIDE in result.reasons
    assert SpotEligibilityReason.DATA_GAPS in result.reasons
    assert SpotEligibilityReason.TERMINAL_EXTENSION in result.reasons


def test_provider_independent_snapshots_serialize_without_futures_fields() -> None:
    strength = SpotRelativeStrengthSnapshot(
        symbol="SOLUSDT",
        return_vs_btc_percentage=4.0,
        return_vs_quote_percentage=12.0,
        lookback_days=30,
    )
    breadth = SpotMarketBreadthSnapshot(
        advancing_assets=70,
        declining_assets=20,
        unchanged_assets=10,
        percentage_above_trend=68.0,
    )

    payload = {"strength": strength.model_dump(), "breadth": breadth.model_dump()}
    assert breadth.observed_assets == 100
    assert SpotScannerMode.ELIGIBLE.value == "eligible"
    assert "leverage" not in str(payload).lower()
    assert "liquidation" not in str(payload).lower()
