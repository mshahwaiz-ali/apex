from __future__ import annotations

from apex.presentation.futures import render_futures_analysis


def _base_payload() -> dict[str, object]:
    return {
        "symbol": "TRX/USDT",
        "decision": "NO_TRADE",
        "reasons": ["Phase 5 selected no trade candidate"],
        "candidate_count": 0,
        "decision_reason_code": "NO_CANDIDATE_GENERATED",
        "market_environment": {
            "primary_regime": "FAILED_BREAKOUT_DOWN",
            "higher_timeframe_bias": "STRONGLY_BEARISH",
            "volatility_state": "NORMAL",
            "extension_state": "EXTREME",
            "long_suitability_score": 15.8,
            "short_suitability_score": 84.2,
            "reason_codes": [
                "PRIMARY_REGIME_FAILED_BREAKOUT_DOWN",
                "HIGHER_TIMEFRAME_BIAS_STRONGLY_BEARISH",
                "EXTENSION_WARNING",
            ],
        },
        "market_strategy_route": {
            "preferred_direction": "short",
            "routing_score": 77.2,
            "strategy_priority": ["liquidity_reversal", "range_reversal"],
        },
        "near_current_entry": {
            "entry_state": "NO_TRADE",
            "actionable_now": False,
            "entry_quality_score": None,
            "chase_risk": None,
            "reasons": ["No approved precision-entry geometry is available"],
        },
        "phase5_diagnostics": {"selected": False},
        "futures_account": {
            "wallet_balance": 100.0,
            "risk_mode": "STANDARD",
            "leverage_mode": "AUTOMATIC",
            "maximum_account_loss_amount": 0.25,
            "margin_mode": "ISOLATED",
        },
    }


def test_default_no_trade_output_is_trader_facing() -> None:
    text = render_futures_analysis(_base_payload())

    assert text.count("TRX/USDT — No Trade") == 1
    assert "Market View" in text
    assert "Trade Decision" in text
    assert "Preferred side" in text
    assert "Short" in text
    assert "No valid setup formed near the current price" in text
    assert "Phase 5" not in text
    assert "Raw candidates" not in text
    assert "NO_CANDIDATE_GENERATED" not in text


def test_warning_codes_are_humanized() -> None:
    text = render_futures_analysis(_base_payload())

    assert "Primary condition is a failed downside breakout" in text
    assert "Higher timeframes are strongly bearish" in text
    assert "Price is extended from its normal trading area" in text
    assert "PRIMARY_REGIME_FAILED_BREAKOUT_DOWN" not in text


def test_verbose_output_includes_humanized_diagnostics() -> None:
    text = render_futures_analysis(_base_payload(), mode="verbose")

    assert "Diagnostics" in text
    assert "Candidates evaluated" in text
    assert "No valid setup formed" in text
    assert "Raw decision code" not in text


def test_debug_output_preserves_internal_diagnostic_visibility() -> None:
    text = render_futures_analysis(_base_payload(), mode="debug")

    assert "Raw decision code" in text
    assert "NO_CANDIDATE_GENERATED" in text
    assert "Phase diagnostics present" in text


def test_wait_for_retest_is_clear() -> None:
    payload = _base_payload()
    payload["decision_reason_code"] = "WAIT_FOR_RETEST"
    payload["near_current_entry"] = {
        "entry_state": "WAIT_FOR_RETEST",
        "actionable_now": False,
        "reasons": ["Price must retest resistance before a short entry"],
    }

    text = render_futures_analysis(payload)

    assert "Wait for retest" in text
    assert "Price must retest the required level before entry" in text


def test_wait_for_reclaim_is_clear() -> None:
    payload = _base_payload()
    payload["decision_reason_code"] = "WAIT_FOR_RECLAIM"
    payload["near_current_entry"] = {
        "entry_state": "WAIT_FOR_RECLAIM",
        "actionable_now": False,
        "reasons": ["Price must reclaim structure before a long entry"],
    }

    text = render_futures_analysis(payload)

    assert "Wait for reclaim" in text
    assert "Price must reclaim the required structure before entry" in text


def test_approved_short_setup_displays_action_first() -> None:
    payload = _base_payload()
    payload.update(
        {
            "decision": "SHORT",
            "strategy": "failed_breakout",
            "current_price": 0.2801,
            "entry_state": "READY_NOW",
            "entry_zone": {
                "low": 0.2795,
                "high": 0.2805,
                "preferred": 0.2800,
                "maximum_chase_price": 0.2788,
            },
            "stop_loss": 0.2830,
            "take_profits": [
                {"price": 0.2760, "risk_reward": 1.5},
                {"price": 0.2720, "risk_reward": 2.8},
            ],
            "confidence_score": 82.4,
            "decision_reason_code": "READY_NOW",
            "near_current_entry": {
                "entry_state": "READY_NOW",
                "actionable_now": True,
                "entry_quality_score": 88.0,
                "chase_risk": "LOW",
                "reasons": ["Short entry is available near the current price"],
            },
        }
    )

    text = render_futures_analysis(payload)

    assert "TRX/USDT — Short Setup" in text
    assert "Action" in text
    assert "Direction" in text
    assert "Short" in text
    assert "Entry zone" in text
    assert "Stop loss" in text
    assert "Take profit 1" in text
    assert "Risk/reward" in text


def test_unavailable_geometry_is_explicit() -> None:
    payload = _base_payload()
    payload.update(
        {
            "decision": "LONG",
            "strategy": "reclaim_entry",
            "entry_state": "APPROACHING_ENTRY",
            "entry_zone": {},
            "take_profits": [],
            "confidence_score": 70.0,
            "near_current_entry": {
                "entry_state": "APPROACHING_ENTRY",
                "actionable_now": False,
            },
        }
    )

    text = render_futures_analysis(payload)

    assert "TRX/USDT — Long Setup" in text
    assert "Entry zone" in text
    assert "Unavailable" in text

def test_execution_rejection_preserves_market_setup_presentation() -> None:
    payload = {
        "symbol": "BTC/USDT",
        "decision": "LONG",
        "strategy": "TREND_PULLBACK",
        "current_price": 100.0,
        "entry_state": "READY_NOW",
        "entry_zone": {
            "low": 99.5,
            "high": 100.5,
            "preferred": 100.0,
            "maximum_chase_price": 101.0,
        },
        "stop_loss": 98.0,
        "take_profits": [{"price": 104.0, "risk_reward": 2.0}],
        "confidence_score": 82.0,
        "opportunity_status": "SETUP_AVAILABLE",
        "execution_approval": {
            "status": "REJECTED",
            "approved": False,
            "eligibility": "REJECTED",
            "reasons": ["account policy lockout: DAILY_DRAWDOWN"],
        },
    }

    rendered = render_futures_analysis(payload)

    assert "BTC/USDT — Long Setup" in rendered
    assert "Execution Approval" in rendered
    assert "Approved to execute" in rendered
    assert "No" in rendered
    assert "account policy lockout: DAILY_DRAWDOWN" in rendered
    assert "No Trade" not in rendered
