"""Tests for canonical spot strategy and planning orchestration."""

from __future__ import annotations

from apex.application.spot_analysis import (
    SPOT_ANALYSIS_SCHEMA_VERSION,
    SpotAnalysisRequest,
    analyze_spot_request,
    spot_analysis_result_to_payload,
)
from apex.config.spot import load_spot_product_config
from apex.config.spot_strategies import load_spot_strategy_config
from apex.domain.spot import SpotAccountInput, SpotMarketRegime
from apex.domain.spot_strategy import SpotStrategyInput
from apex.domain.spot_structure import SpotExtensionState, SpotTrendState


def _account() -> SpotAccountInput:
    return SpotAccountInput(
        quote_asset="USDT",
        available_quote_balance=10_000.0,
        total_spot_equity=10_000.0,
        current_spot_exposure=0.0,
        open_position_count=0,
        balances=(),
    )


def _strategy_input(*, allow_new_entries: bool = True) -> SpotStrategyInput:
    return SpotStrategyInput(
        symbol="BTCUSDT",
        current_price=100.0,
        market_regime=SpotMarketRegime.RISK_ON,
        allow_new_entries=allow_new_entries,
        structure_trend=SpotTrendState.UPTREND,
        extension=SpotExtensionState.NORMAL,
        support_price=95.0,
        resistance_price=110.0,
        demand_lower=98.0,
        demand_upper=102.0,
        relative_strength_percentage=5.0,
        volume_ratio=1.8,
        pullback_depth_percentage=6.0,
        range_width_percentage=10.0,
        breakout_confirmed=False,
        retest_held=False,
        accumulation_confirmed=False,
        liquidity_sweep_confirmed=False,
        daily_recovery_confirmed=False,
        capitulation_recovery_confirmed=False,
    )


def _request(*, allow_new_entries: bool = True) -> SpotAnalysisRequest:
    return SpotAnalysisRequest(
        strategy_input=_strategy_input(allow_new_entries=allow_new_entries),
        account=_account(),
        support_price=95.0,
        resistance_price=110.0,
        deeper_support_price=92.0,
        recovery_entry_price=94.0,
        correlated_sector_exposure=0.0,
    )


def test_approved_strategy_builds_bounded_spot_plan() -> None:
    result = analyze_spot_request(
        _request(),
        product_config=load_spot_product_config("config/spot.yaml"),
        strategy_config=load_spot_strategy_config("config/spot_strategies.yaml"),
    )
    payload = spot_analysis_result_to_payload(result)

    assert result.routing.selected is not None
    assert result.planning is not None
    assert payload["schema_version"] == SPOT_ANALYSIS_SCHEMA_VERSION
    assert payload["selected_strategy"]["decision"] == "APPROVE"
    assert payload["planning"]["entry_plan"]["direction"] == "LONG"
    assert payload["planning"]["entry_plan"]["side"] == "BUY"
    assert "leverage" not in payload["planning"]["position_plan"]
    assert "liquidation" not in payload["planning"]["position_plan"]


def test_blocked_regime_returns_candidates_without_plan() -> None:
    result = analyze_spot_request(
        _request(allow_new_entries=False),
        product_config=load_spot_product_config("config/spot.yaml"),
        strategy_config=load_spot_strategy_config("config/spot_strategies.yaml"),
    )
    payload = spot_analysis_result_to_payload(result)

    assert result.routing.selected is None
    assert result.planning is None
    assert payload["selected_strategy"] is None
    assert payload["planning"] is None
    assert len(payload["candidates"]) == 6
