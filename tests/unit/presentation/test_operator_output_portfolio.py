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
            "overall_trade_quality": 0.78,
            "execution_quality": 0.72,
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
    follow_up = _opportunity(
        opportunity_id="btc-follow-up-long",
        role="follow_up",
        setup=_setup(
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
        ),
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
    assert "Nearby opportunity" in text
    assert "Follow-up opportunity" in text
    assert "Runner management" in text
    assert "Setup plan" in text


def test_analysis_renders_each_opportunity_identity_and_geometry() -> None:
    text = render_analysis(_portfolio_payload())

    for opportunity_id in (
        "btc-current-long",
        "btc-nearby-short",
        "btc-follow-up-long",
        "btc-runner-long",
    ):
        assert opportunity_id in text

    assert "Maximum chase" in text
    assert "Stop / invalidation" in text
    assert "TP1" in text
    assert "Trade quality" in text
    assert "Execution quality" in text
    assert "Main risk" in text


def test_analysis_renders_methodology_verdict_in_snapshot() -> None:
    text = render_analysis(_portfolio_payload())

    assert "Methodology verdict" in text
    assert "Allowed" in text


def test_analysis_renders_truthful_no_valid_setup_plan() -> None:
    payload = {
        "symbol": "ETHUSDT",
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

    assert "NO TRADE RIGHT NOW" in text
    assert "Setup plan" in text
    assert "NO VALID SETUP YET" in text
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
