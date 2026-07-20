from __future__ import annotations

from apex.presentation.operator_output import render_scan


def _opportunity(*, opportunity_id: str, category: str, state: str) -> dict[str, object]:
    setup = {
        "direction": "long",
        "strategy": "breakout_retest",
        "entry_status": state,
        "execution_allowed_now": state == "READY_NOW",
        "entry": {
            "current_price": 100.0,
            "lower": 99.0,
            "upper": 101.0,
            "preferred": 100.0 if category == "current" else 103.0,
            "maximum_chase_price": 102.0,
        },
        "stop_loss": {"price": 97.0},
        "take_profits": [{"price": 106.0, "risk_reward": 2.0}],
        "quality_dimensions": {
            "setup_quality": 0.82,
            "execution_quality": 0.78,
            "target_quality": 0.74,
        },
        "warnings": ["1h resistance above TP2"],
    }
    return {
        **setup,
        "opportunity_id": opportunity_id,
        "category": category,
        "sequence_role": category,
        "methodology_verdict": {"status": "allowed"},
        "setup": setup,
    }


def _result(symbol: str, opportunities: list[dict[str, object]]) -> dict[str, object]:
    return {
        "symbol": symbol,
        "methodology_verdict": {"status": "allowed"},
        "opportunity_portfolio": {
            "symbol": symbol,
            "opportunity_count": len(opportunities),
            "opportunities": opportunities,
        },
        "setup_plan": {
            "status": "no_valid_setup_yet" if not opportunities else "opportunities_available",
            "geometry_available": bool(opportunities),
            "current_state": "mid-range conflict",
            "long_trigger": None,
            "short_trigger": None,
            "invalidation": None,
            "main_risk": "no clear target room",
        },
        "reasons": ["no clear target room"],
    }


def test_render_scan_expands_complete_portfolios_in_locked_order() -> None:
    payload = {
        "total_symbol_count": 8,
        "filtered_symbol_count": 6,
        "displayed_symbol_count": 3,
        "total_analysis_count": 3,
        "retained_opportunity_count": 5,
        "displayed_opportunity_count": 4,
        "direction_filter": "both",
        "failures": {"BADUSDT": "Binance timeout"},
        "results": [
            _result(
                "BTCUSDT",
                [
                    _opportunity(
                        opportunity_id="btc-now",
                        category="current",
                        state="READY_NOW",
                    ),
                    _opportunity(
                        opportunity_id="btc-confirm",
                        category="current",
                        state="WAIT_FOR_RETEST",
                    ),
                    _opportunity(
                        opportunity_id="btc-nearby",
                        category="nearby",
                        state="APPROACHING_ENTRY",
                    ),
                    _opportunity(
                        opportunity_id="btc-follow",
                        category="follow_up",
                        state="WATCH",
                    ),
                ],
            ),
            _result("ETHUSDT", []),
        ],
    }

    rendered = render_scan(payload)

    enter_heading = rendered.index("┌─ Enter at CMP")
    confirmation_heading = rendered.index("┌─ Confirmation entry")
    nearby_heading = rendered.index("┌─ Nearby entry")
    developing_heading = rendered.index("┌─ Developing / follow-up")

    assert enter_heading < confirmation_heading
    assert confirmation_heading < nearby_heading
    assert nearby_heading < developing_heading
    assert "btc-now" in rendered
    assert "btc-confirm" in rendered
    assert "btc-nearby" in rendered
    assert "btc-follow" in rendered
    assert "Entry distance" in rendered
    assert "Maximum chase" in rendered
    assert "Methodology" in rendered
    assert "Quality" in rendered
    assert "Setup" in rendered
    assert "Execution" in rendered
    assert "Target" in rendered
    assert "/100" in rendered
    assert "No current trade — Setup plans (1)" in rendered
    assert "ETHUSDT — NO VALID SETUP YET" in rendered
    assert "Showing 3 of 6 filtered symbols." in rendered
    assert "Showing 4 of 5 retained opportunities." in rendered
    assert "BADUSDT — Binance timeout" in rendered


def test_render_scan_summary_distinguishes_symbols_and_opportunities() -> None:
    payload = {
        "total_symbol_count": 10,
        "filtered_symbol_count": 7,
        "displayed_symbol_count": 2,
        "total_analysis_count": 2,
        "retained_opportunity_count": 6,
        "displayed_opportunity_count": 3,
        "direction_filter": "long",
        "failures": {},
        "results": [
            _result(
                "BTCUSDT",
                [
                    _opportunity(
                        opportunity_id="btc-now",
                        category="current",
                        state="READY_NOW",
                    ),
                    _opportunity(
                        opportunity_id="btc-nearby",
                        category="nearby",
                        state="APPROACHING_ENTRY",
                    ),
                ],
            ),
            _result("ETHUSDT", []),
        ],
    }

    rendered = render_scan(payload)

    assert "Markets discovered" in rendered and "10" in rendered
    assert "Symbols shortlisted" in rendered and "2" in rendered
    assert "Opportunities retained" in rendered and "6" in rendered
    assert "Opportunities displayed" in rendered and "3" in rendered
    assert "Direction filter" in rendered and "Long" in rendered
