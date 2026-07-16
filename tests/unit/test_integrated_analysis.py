"""Integration-boundary tests for market-environment-aware analysis output."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import pytest

from apex.application import analysis as base_analysis
from apex.application.integrated_analysis import (
    ScanResult,
    format_symbol_text,
    serialize_scan_result,
    serialize_symbol_analysis,
)
from apex.domain import MarketCategory
from apex.market_environment import (
    ConflictState,
    ExtensionState,
    HigherTimeframeBias,
    InputCompleteness,
    MarketEnvironment,
    MarketRegime,
    VolatilityState,
)


def _environment() -> MarketEnvironment:
    return MarketEnvironment(
        primary_regime=MarketRegime.TREND_UP,
        higher_timeframe_bias=HigherTimeframeBias.BULLISH,
        execution_timeframe="5m",
        entry_timeframe="1m",
        alignment_score=78.0,
        conflict_score=12.0,
        conflict_state=ConflictState.NONE,
        volatility_state=VolatilityState.EXPANDING,
        extension_state=ExtensionState.MODERATE,
        tradeable=True,
        long_suitability_score=78.0,
        short_suitability_score=22.0,
        reason_codes=("ENVIRONMENT_TRADEABLE",),
        reasons=("Environment meets configured tradeability thresholds",),
        missing_timeframes=(),
        input_completeness=InputCompleteness.COMPLETE,
        timeframe_regimes={},
    )


def _analysis_object(environment: MarketEnvironment | None) -> base_analysis.SymbolAnalysis:
    return cast(
        base_analysis.SymbolAnalysis,
        SimpleNamespace(
            symbol="BTC/USDT",
            generated_at=datetime(2026, 7, 16, tzinfo=UTC),
            scanner_type=MarketCategory.NORMAL_MARKET,
            market_environment=environment,
            assessment=SimpleNamespace(setup=None),
        ),
    )


def test_symbol_json_contains_market_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        base_analysis,
        "serialize_symbol_analysis",
        lambda analysis: {"symbol": analysis.symbol, "decision": "NO_TRADE", "reasons": []},
    )

    payload = serialize_symbol_analysis(_analysis_object(_environment()))

    assert payload["market_environment"] == {
        "primary_regime": "TREND_UP",
        "higher_timeframe_bias": "BULLISH",
        "execution_timeframe": "5m",
        "entry_timeframe": "1m",
        "alignment_score": 78.0,
        "conflict_score": 12.0,
        "conflict_state": "NONE",
        "volatility_state": "EXPANDING",
        "extension_state": "MODERATE",
        "tradeable": True,
        "long_suitability_score": 78.0,
        "short_suitability_score": 22.0,
        "reason_codes": ["ENVIRONMENT_TRADEABLE"],
        "reasons": ["Environment meets configured tradeability thresholds"],
        "missing_timeframes": [],
        "input_completeness": "COMPLETE",
        "timeframe_regimes": {},
    }


def test_symbol_json_preserves_legacy_analysis_without_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        base_analysis,
        "serialize_symbol_analysis",
        lambda analysis: {"symbol": analysis.symbol, "decision": "NO_TRADE", "reasons": []},
    )

    payload = serialize_symbol_analysis(_analysis_object(None))

    assert payload["market_environment"] is None


def test_scanner_json_nests_market_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        base_analysis,
        "serialize_symbol_analysis",
        lambda analysis: {"symbol": analysis.symbol, "decision": "NO_TRADE", "reasons": []},
    )
    analysis = _analysis_object(_environment())
    result = ScanResult(
        generated_at=datetime(2026, 7, 16, tzinfo=UTC),
        analyses=(analysis,),
        failures={},
    )

    payload = serialize_scan_result(result)

    assert payload["results"][0]["market_environment"]["primary_regime"] == "TREND_UP"
    assert payload["results"][0]["market_environment"]["execution_timeframe"] == "5m"


def test_human_text_contains_operational_environment_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(base_analysis, "format_symbol_text", lambda analysis: "BTC/USDT: NO_TRADE")

    text = format_symbol_text(_analysis_object(_environment()))

    assert "Regime: TREND_UP" in text
    assert "HTF bias: BULLISH" in text
    assert "Execution / entry: 5m / 1m" in text
    assert "Volatility / extension: EXPANDING / MODERATE" in text
    assert "Long / short suitability: 78.0 / 22.0" in text
    assert "Tradeable: yes" in text
