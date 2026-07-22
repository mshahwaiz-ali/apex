from __future__ import annotations

from apex.presentation.operator_output import render_analysis


def _setup(
    *,
    candidate_id: str,
    direction: str,
    strategy: str,
    entry_status: str,
    current_price: float,
    lower: float,
    upper: float,
    preferred: float,
    maximum_chase: float,
    stop: float,
    target: float,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "direction": direction,
        "strategy": strategy,
        "entry_status": entry_status,
        "confidence_score": 78.0,
        "execution_allowed_now": entry_status == "READY_NOW",
        "entry": {
            "current_price": current_price,
            "lower": lower,
            "upper": upper,
            "preferred": preferred,
            "maximum_chase_price": maximum_chase,
        },
        "stop_loss": {
            "price": stop,
            "distance_pct": 2.0,
            "rationale": ["structure"],
        },
        "take_profits": [
            {
                "label": "TP1",
                "price": target,
                "risk_reward": 2.0,
                "rationale": ["liquidity"],
            }
        ],
        "quality_dimensions": {
            "pattern_confidence": 0.76,
            "directional_alignment": 0.64,
            "setup_quality": 0.81,
            "execution_quality": 0.72,
            "target_quality": 0.74,
            "timing_quality": 0.69,
            "data_confidence": 0.93,
            "overall_trade_quality": 0.78,
        },
        "layered_state": {
            "timeframe_relationship": "mixed",
            "relationship_severity": "moderate",
            "continuation_state": "fresh_continuation",
        },
        "warnings": ["liquidity can deteriorate"],
    }


def _opportunity(
    *,
    opportunity_id: str,
    role: str,
    setup: dict[str, object],
) -> dict[str, object]:
    return {
        **setup,
        "opportunity_id": opportunity_id,
        "category": role,
        "sequence_role": role,
        "direction": setup["direction"],
        "strategy": setup["strategy"],
        "lane": role,
        "rank_score": 82.5,
        "ranking": {"rank_score": 82.5},
        "setup": setup,
    }


def _portfolio_payload() -> dict[str, object]:
    current = _opportunity(
        opportunity_id="btc-current-long",
        role="current",
        setup=_setup(
            candidate_id="btc-current-long",
            direction="long",
            strategy="breakout_continuation",
            entry_status="READY_NOW",
            current_price=100.0,
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            maximum_chase=102.0,
            stop=97.0,
            target=106.0,
        ),
    )
    nearby = _opportunity(
        opportunity_id="btc-nearby-short",
        role="nearby",
        setup=_setup(
            candidate_id="btc-nearby-short",
            direction="short",
            strategy="failed_breakout",
            entry_status="WAIT_FOR_RETEST",
            current_price=100.0,
            lower=103.0,
            upper=104.0,
            preferred=103.5,
            maximum_chase=102.0,
            stop=106.0,
            target=97.0,
        ),
    )
    follow_up_setup = _setup(
        candidate_id="btc-follow-up-long",
        direction="long",
        strategy="sweep_reversal",
        entry_status="APPROACHING_ENTRY",
        current_price=100.0,
        lower=96.0,
        upper=97.0,
        preferred=96.5,
        maximum_chase=98.0,
        stop=94.0,
        target=103.0,
    )
    follow_up_setup["conditional_plan"] = {
        "trigger": {
            "type": "reclaim_close",
            "level": 96.5,
            "condition": "price reclaims the preferred level after the liquidity sweep",
            "confirmation_timeframe": "5m",
        },
        "pre_entry_invalidation": {
            "price": 94.5,
            "condition": (
                "price reaches or closes below structural invalidation before activation"
            ),
            "rationale": ["raw thesis invalidation"],
        },
        "conditional_order_eligible": False,
        "recommended_order_intent": "alert_only",
        "reason_not_executable_now": "activation is incomplete",
        "expiry": {
            "seconds": 900,
            "bars": 6,
            "reason": "candidate activation window",
            "validity": "15 minutes",
        },
        "geometry": {
            "geometry_basis": "candidate_entry_zone",
            "entry_source": "strategy_generated_liquidity_boundary_recovery",
            "trigger_matches_preferred_entry": True,
            "stop_basis": "structural_invalidation_buffered_from_candidate_entry",
            "targets_basis": "strategy_supplied_structural_targets",
            "geometry_is_trigger_relative": True,
        },
    }
    follow_up = _opportunity(
        opportunity_id="btc-follow-up-long",
        role="follow_up",
        setup=follow_up_setup,
    )
    runner = _opportunity(
        opportunity_id="btc-runner-long",
        role="runner",
        setup=_setup(
            candidate_id="btc-runner-long",
            direction="long",
            strategy="momentum_continuation",
            entry_status="READY_NOW",
            current_price=100.0,
            lower=98.0,
            upper=100.0,
            preferred=99.0,
            maximum_chase=101.0,
            stop=96.0,
            target=108.0,
        ),
    )

    return {
        "symbol": "BTCUSDT",
        "generated_at": "2026-07-22T10:15:30+00:00",
        "methodology_verdict": {
            "status": "allowed",
            "allowed": True,
            "authoritative": True,
        },
        "opportunity_portfolio": {
            "symbol": "BTCUSDT",
            "cmp": 100.0,
            "analysis_mode": "analyze_full",
            "decision": "actionable_at_cmp",
            "opportunity_count": 4,
            "current_opportunities": [current],
            "nearby_opportunities": [nearby],
            "follow_up_opportunities": [follow_up],
            "runner_opportunities": [runner],
            "opportunities": [current, nearby, follow_up, runner],
        },
        "setup_plan": {
            "status": "actionable_at_cmp",
            "geometry_available": True,
            "opportunity_count": 4,
            "primary_opportunity_id": "btc-current-long",
        },
    }


def test_analysis_renders_complete_portfolio_sections() -> None:
    text = render_analysis(_portfolio_payload())

    assert "Market snapshot" in text
    assert "Current opportunities" in text
    assert "Conditional monitoring" in text
    assert "Follow-up opportunity" in text
    assert "Runner management" in text
    assert "Setup plan" in text


def test_analysis_renders_operator_context_and_geometry_without_raw_ids() -> None:
    text = render_analysis(_portfolio_payload())

    for opportunity_id in (
        "btc-current-long",
        "btc-nearby-short",
        "btc-follow-up-long",
        "btc-runner-long",
    ):
        assert opportunity_id not in text

    assert "Opportunity #1" in text
    assert "Signal generated  2026-07-22 10:15:30 UTC" in text
    assert text.index("Opportunity #1") < text.index("Signal generated")
    assert text.index("Signal generated") < text.index("Breakout continuation")
    assert "Breakout continuation · Current · Ready now" in text
    assert "Failed breakout · Nearby · Wait for retest" in text
    assert "Mixed (moderate) · Fresh continuation" in text
    assert "Maximum chase" in text
    assert "Ideal entry" in text
    assert "Entry range" in text
    assert "Stop loss" in text
    assert "TP1" in text
    assert "2.00R" in text
    assert "target quality" in text
    assert "0.7/100" in text
    assert "Pattern confidence" in text
    assert "Setup quality" in text
    assert "Execution quality" in text
    assert "Target quality" in text
    assert "HTF alignment" in text
    assert "Overall trade quality" in text
    assert "Rank score" in text
    assert "Main risk" in text
    assert "BTCUSDT — LONG" in text
    assert "BTCUSDT — SHORT" in text


def test_analysis_renders_methodology_verdict_in_snapshot() -> None:
    text = render_analysis(_portfolio_payload())

    assert "Methodology verdict" in text
    assert "Allowed" in text


def test_analysis_renders_truthful_no_valid_setup_plan() -> None:
    payload = {
        "symbol": "ETHUSDT",
        "generated_at": "2026-07-22T10:15:30+00:00",
        "reasons": ["mid-range conflicting structure"],
        "methodology_verdict": {
            "status": "unavailable",
            "allowed": None,
            "authoritative": False,
        },
        "opportunity_portfolio": {
            "symbol": "ETHUSDT",
            "cmp": 2500.0,
            "analysis_mode": "analyze_full",
            "decision": "no_valid_setup",
            "opportunity_count": 0,
            "current_opportunities": [],
            "nearby_opportunities": [],
            "follow_up_opportunities": [],
            "runner_opportunities": [],
            "opportunities": [],
        },
        "setup_plan": {
            "status": "no_valid_setup_yet",
            "geometry_available": False,
            "current_state": "mid-range conflicting structure",
            "long_trigger": None,
            "short_trigger": None,
            "invalidation": None,
            "stop": None,
            "targets": [],
            "main_risk": "mid-range conflicting structure",
        },
    }

    text = render_analysis(payload)

    assert "NO TRADE RIGHT NOW" not in text
    assert "Setup plan" in text
    assert "NO VALID SETUP YET" in text
    assert "Signal generated" in text
    assert "2026-07-22 10:15:30 UTC" in text
    assert "mid-range conflicting structure" in text
    assert "Long trigger" in text
    assert "Short trigger" in text


def test_analysis_legacy_payload_still_uses_compatibility_fallback() -> None:
    payload = {
        "symbol": "SOLUSDT",
        "setup": _setup(
            candidate_id="legacy-sol",
            direction="long",
            strategy="trend_pullback",
            entry_status="READY_NOW",
            current_price=150.0,
            lower=149.0,
            upper=151.0,
            preferred=150.0,
            maximum_chase=152.0,
            stop=146.0,
            target=158.0,
        ),
    }

    text = render_analysis(payload)

    assert "APEX ANALYSIS" in text
    assert "Trade plan" in text
    assert "Current opportunities" not in text


def test_analysis_renders_conditional_follow_up_details() -> None:
    text = render_analysis(_portfolio_payload())

    assert "Activation trigger" in text
    assert "Reclaim close" in text
    assert "Pre-entry invalidation" in text
    assert "94.5" in text
    assert "Order intent" in text
    assert "Alert only" in text
    assert "Resting order authorized" in text
    assert "Conditional validity" in text
    assert "15 minutes" in text
    assert "candidate activation window" in text
