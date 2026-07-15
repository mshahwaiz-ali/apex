from __future__ import annotations

from apex.application.spot_analysis import SpotAnalysisRequest, analyze_spot_request
from apex.application.spot_historical_replay import (
    _evaluate_historical_eligibility,
    _historical_support_geometry,
)
from apex.config.spot import load_spot_product_config
from apex.config.spot_strategies import load_spot_strategy_config
from apex.domain.spot import SpotAccountInput, SpotMarketRegime
from apex.domain.spot_market import (
    SpotEligibilityReason,
    SpotEligibilityThresholds,
    SpotMarketMetadata,
)
from apex.domain.spot_strategy import SpotStrategyDecision, SpotStrategyInput
from apex.domain.spot_structure import SpotExtensionState, SpotTrendState


def _thresholds() -> SpotEligibilityThresholds:
    return SpotEligibilityThresholds(
        minimum_quote_volume_24h=10_000_000,
        minimum_market_age_days=None,
        maximum_spread_percentage=0.25,
        minimum_candle_count=180,
        minimum_atr_percentage=0.1,
        maximum_downside_volatility_percentage=12.0,
    )


def test_historical_missing_spread_is_disclosed_without_false_wide_spread() -> None:
    result = _evaluate_historical_eligibility(
        SpotMarketMetadata(
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            quote_volume_24h=500_000_000,
            spread_percentage=None,
            market_age_days=None,
            available_candle_count=200,
            atr_percentage=2.0,
            downside_volatility_percentage=4.0,
        ),
        _thresholds(),
    )

    assert result.eligible is True
    assert result.reasons == (SpotEligibilityReason.ELIGIBLE.value,)
    assert SpotEligibilityReason.SPREAD_TOO_WIDE.value not in result.reasons
    assert result.unavailable_fields == ("bid_ask_spread",)


def test_historical_observed_wide_spread_remains_ineligible() -> None:
    result = _evaluate_historical_eligibility(
        SpotMarketMetadata(
            symbol="BTCUSDT",
            base_asset="BTC",
            quote_asset="USDT",
            quote_volume_24h=500_000_000,
            spread_percentage=0.5,
            market_age_days=None,
            available_candle_count=200,
            atr_percentage=2.0,
            downside_volatility_percentage=4.0,
        ),
        _thresholds(),
    )

    assert result.eligible is False
    assert SpotEligibilityReason.SPREAD_TOO_WIDE.value in result.reasons
    assert result.unavailable_fields == ()


def test_historical_support_geometry_is_strictly_below_all_entries() -> None:
    recovery, deeper_support = _historical_support_geometry(
        current_price=100.0,
        canonical_support_lower=96.0,
        recovery_reference=97.5,
        atr=3.0,
    )

    assert recovery <= 100.0
    assert deeper_support < 96.0
    assert deeper_support < recovery
    assert deeper_support < 100.0


def test_incompatible_approved_invalidation_is_rejected_before_planning() -> None:
    product_config = load_spot_product_config("config/spot.yaml")
    strategy_config = load_spot_strategy_config("config/spot_strategies.yaml")
    strategy_input = SpotStrategyInput(
        symbol="BTCUSDT",
        current_price=100.0,
        market_regime=SpotMarketRegime.RISK_ON,
        allow_new_entries=True,
        structure_trend=SpotTrendState.UPTREND,
        extension=SpotExtensionState.NORMAL,
        support_price=95.0,
        resistance_price=110.0,
        demand_lower=98.0,
        demand_upper=102.0,
        relative_strength_percentage=5.0,
        volume_ratio=2.0,
        pullback_depth_percentage=5.0,
    )
    result = analyze_spot_request(
        SpotAnalysisRequest(
            strategy_input=strategy_input,
            account=SpotAccountInput(
                quote_asset="USDT",
                available_quote_balance=10_000.0,
                total_spot_equity=10_000.0,
            ),
            support_price=95.0,
            resistance_price=110.0,
            deeper_support_price=90.0,
            recovery_entry_price=97.0,
        ),
        product_config=product_config,
        strategy_config=strategy_config,
    )

    assert result.planning is None
    assert result.routing.selected is None
    assert any(
        candidate.decision is SpotStrategyDecision.REJECT
        and "strategy invalidation is not below all planned spot entries"
        in candidate.rejection_reasons
        for candidate in result.routing.candidates
    )
