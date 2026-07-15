"""Tests for the provider-independent S2-to-S4 spot bridge."""

from __future__ import annotations

from apex.application.spot_analysis import spot_analysis_result_to_payload
from apex.application.spot_orchestration import (
    SpotOrchestrationInput,
    SpotSetupEvidence,
    analyze_spot_orchestration,
    build_spot_strategy_input,
)
from apex.config.spot import load_spot_product_config
from apex.config.spot_strategies import load_spot_strategy_config
from apex.domain.spot import SpotAccountInput, SpotMarketRegime
from apex.domain.spot_structure import (
    SpotExtensionState,
    SpotPriceZone,
    SpotRegimeResult,
    SpotStructureResult,
    SpotTimeframeStructure,
    SpotTrendState,
    SpotZoneType,
)


def _zone(zone_type: SpotZoneType, lower: float, upper: float) -> SpotPriceZone:
    return SpotPriceZone(
        zone_type=zone_type,
        lower=lower,
        upper=upper,
        source_timeframe="1d",
    )


def _structure(*, extension: SpotExtensionState = SpotExtensionState.NORMAL) -> SpotStructureResult:
    timeframe = SpotTimeframeStructure(
        timeframe="1d",
        trend=SpotTrendState.UPTREND,
        extension=extension,
        support=_zone(SpotZoneType.SUPPORT, 95.0, 96.0),
        resistance=_zone(SpotZoneType.RESISTANCE, 110.0, 111.0),
        demand=_zone(SpotZoneType.DEMAND, 98.0, 102.0),
        evidence=("trend=UPTREND",),
    )
    return SpotStructureResult(
        trend=SpotTrendState.UPTREND,
        extension=extension,
        timeframes=(timeframe,),
        relative_strength_score=5.0,
        evidence=("weighted_trend_score=1.000",),
    )


def _account() -> SpotAccountInput:
    return SpotAccountInput(
        quote_asset="USDT",
        available_quote_balance=10_000.0,
        total_spot_equity=10_000.0,
    )


def _input(
    *,
    allow_new_entries: bool = True,
    regime: SpotMarketRegime = SpotMarketRegime.RISK_ON,
    extension: SpotExtensionState = SpotExtensionState.NORMAL,
    evidence: SpotSetupEvidence | None = None,
) -> SpotOrchestrationInput:
    return SpotOrchestrationInput(
        symbol="BTCUSDT",
        current_price=100.0,
        structure=_structure(extension=extension),
        regime=SpotRegimeResult(
            regime=regime,
            allow_new_entries=allow_new_entries,
            evidence=("canonical regime",),
        ),
        account=_account(),
        evidence=evidence or SpotSetupEvidence(),
        deeper_support_price=94.5,
        recovery_entry_price=96.0,
    )


def _analyze(inputs: SpotOrchestrationInput):
    return analyze_spot_orchestration(
        inputs,
        product_config=load_spot_product_config("config/spot.yaml"),
        strategy_config=load_spot_strategy_config("config/spot_strategies.yaml"),
    )


def test_bullish_trend_pullback_becomes_approved_and_planned() -> None:
    result = _analyze(
        _input(evidence=SpotSetupEvidence(volume_ratio=1.8, pullback_depth_percentage=6.0))
    )

    assert result.routing.selected is not None
    assert result.routing.selected.strategy == "higher_timeframe_trend_pullback"
    assert result.planning is not None


def test_risk_off_regime_blocks_planning() -> None:
    result = _analyze(
        _input(
            allow_new_entries=False,
            regime=SpotMarketRegime.RISK_OFF,
            evidence=SpotSetupEvidence(pullback_depth_percentage=6.0),
        )
    )

    assert result.routing.selected is None
    assert result.planning is None


def test_terminal_extension_blocks_planning() -> None:
    result = _analyze(
        _input(
            extension=SpotExtensionState.TERMINAL,
            evidence=SpotSetupEvidence(pullback_depth_percentage=6.0),
        )
    )

    assert result.routing.selected is None
    assert result.planning is None


def test_missing_optional_evidence_is_not_fabricated() -> None:
    strategy_input = build_spot_strategy_input(_input())
    result = _analyze(_input())

    assert strategy_input.volume_ratio == 0.0
    assert strategy_input.pullback_depth_percentage is None
    assert strategy_input.breakout_confirmed is False
    assert result.planning is None


def test_repeated_execution_is_deterministic() -> None:
    inputs = _input(
        evidence=SpotSetupEvidence(volume_ratio=1.8, pullback_depth_percentage=6.0)
    )

    first = spot_analysis_result_to_payload(_analyze(inputs))
    second = spot_analysis_result_to_payload(_analyze(inputs))

    assert first == second
