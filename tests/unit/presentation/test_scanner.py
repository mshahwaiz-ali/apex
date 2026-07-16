from __future__ import annotations

from apex.presentation.scanner import render_futures_scan


def _no_trade(symbol: str, *, preferred: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "decision": "NO_TRADE",
        "reasons": ["No approved precision-entry geometry is available"],
        "decision_reason_code": "NO_CANDIDATE_GENERATED",
        "market_environment": {
            "higher_timeframe_bias": "STRONGLY_BEARISH",
            "primary_regime": "FAILED_BREAKOUT_DOWN",
            "volatility_state": "NORMAL",
            "extension_state": "EXTREME",
            "long_suitability_score": 20.0,
            "short_suitability_score": 80.0,
        },
        "market_strategy_route": {"preferred_direction": preferred},
        "near_current_entry": {"entry_state": "NO_TRADE"},
    }


def _approved(symbol: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "decision": "SHORT",
        "strategy": "FAILED_BREAKOUT",
        "current_price": 100.0,
        "entry_state": "READY_NOW",
        "entry_zone": {
            "low": 99.5,
            "high": 100.5,
            "preferred": 100.0,
            "maximum_chase_price": 99.0,
        },
        "stop_loss": 102.0,
        "take_profits": [{"price": 97.0, "risk_reward": 1.5}],
        "confidence_score": 82.0,
        "market_environment": {
            "higher_timeframe_bias": "STRONGLY_BEARISH",
            "primary_regime": "FAILED_BREAKOUT_DOWN",
            "volatility_state": "NORMAL",
            "extension_state": "NORMAL",
            "long_suitability_score": 18.0,
            "short_suitability_score": 82.0,
        },
        "market_strategy_route": {"preferred_direction": "short"},
        "near_current_entry": {
            "entry_state": "READY_NOW",
            "actionable_now": True,
            "entry_quality_score": 86.0,
            "chase_risk": "LOW",
        },
    }


def test_scan_summary_and_market_separators_are_clear() -> None:
    payload = {
        "scanner_mode": "all",
        "risk_mode": "STANDARD",
        "results": [_approved("BTC/USDT"), _no_trade("ETH/USDT", preferred="short")],
        "failures": {},
    }

    text = render_futures_scan(payload)

    assert "Apex Futures Scan" in text
    assert "Markets analyzed  : 2" in text
    assert "Actionable setups : 1" in text
    assert "No-trade markets  : 1" in text
    assert "1. BTC/USDT — Short" in text
    assert "═" * 56 in text
    assert text.count("BTC/USDT — Short Setup") == 1
    assert text.count("ETH/USDT — No Trade") == 1


def test_empty_actionable_section_explains_bias_is_not_entry() -> None:
    payload = {
        "scanner_mode": "normal",
        "risk_mode": "AGGRESSIVE",
        "results": [_no_trade("TRX/USDT", preferred="short")],
        "failures": {},
    }

    text = render_futures_scan(payload)

    assert "None. Directional bias may still exist" in text
    assert "no executable entry passed the current rules" in text
    assert "Preferred side    : Short" in text


def test_failures_are_grouped_separately() -> None:
    payload = {
        "scanner_mode": "normal",
        "risk_mode": "STANDARD",
        "results": [],
        "failures": {"SOL/USDT": "provider timeout"},
    }

    text = render_futures_scan(payload)

    assert "Failures" in text
    assert "SOL/USDT: provider timeout" in text
    assert "No market results were returned" in text


def test_verbose_mode_reuses_symbol_diagnostics() -> None:
    payload = {
        "scanner_mode": "normal",
        "risk_mode": "STANDARD",
        "results": [_no_trade("TRX/USDT", preferred="short")],
        "failures": {},
    }

    text = render_futures_scan(payload, mode="verbose")

    assert "Diagnostics" in text
    assert "Raw decision code" not in text


def test_debug_mode_exposes_raw_symbol_diagnostics() -> None:
    payload = {
        "scanner_mode": "normal",
        "risk_mode": "STANDARD",
        "results": [_no_trade("TRX/USDT", preferred="short")],
        "failures": {},
    }

    text = render_futures_scan(payload, mode="debug")

    assert "Raw decision code" in text
    assert "NO_CANDIDATE_GENERATED" in text
