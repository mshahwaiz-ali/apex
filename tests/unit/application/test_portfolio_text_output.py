from __future__ import annotations

from types import SimpleNamespace

from apex.application import decision_analysis


def _opportunity(
    opportunity_id: str,
    direction: str,
    strategy: str,
    status: str,
    lower: float,
    upper: float,
    preferred: float,
    stop: float,
) -> SimpleNamespace:
    return SimpleNamespace(
        opportunity_id=opportunity_id,
        setup=SimpleNamespace(
            direction=SimpleNamespace(value=direction),
            strategy=SimpleNamespace(value=strategy),
            entry_status=SimpleNamespace(value=status),
            entry=SimpleNamespace(
                lower=lower,
                upper=upper,
                preferred=preferred,
            ),
            stop_loss=SimpleNamespace(price=stop),
        ),
    )


def test_portfolio_summary_lists_fixed_slots_and_follow_ups() -> None:
    current_long = _opportunity(
        "current-long",
        "long",
        "breakout_continuation",
        "READY_NOW",
        99.0,
        101.0,
        100.0,
        97.0,
    )
    nearby_short = _opportunity(
        "nearby-short",
        "short",
        "failed_breakout",
        "RETEST_PREFERRED",
        103.0,
        104.0,
        103.5,
        106.0,
    )
    follow_up = _opportunity(
        "follow-up",
        "short",
        "sweep_reversal",
        "DEVELOPING",
        105.0,
        106.0,
        105.5,
        108.0,
    )
    analysis = SimpleNamespace(
        opportunity_portfolio=SimpleNamespace(
            current_long=current_long,
            current_short=None,
            nearby_long=None,
            nearby_short=nearby_short,
            follow_up_opportunities=(follow_up,),
            all_opportunities=(current_long, nearby_short, follow_up),
        )
    )

    lines = decision_analysis._portfolio_summary_lines(analysis)

    assert lines[0] == "Opportunity portfolio: 3"
    assert lines[1].startswith("Current long: LONG | breakout_continuation")
    assert lines[2] == "Current short: none"
    assert lines[3] == "Nearby long: none"
    assert lines[4].startswith("Nearby short: SHORT | failed_breakout")
    assert lines[5] == "Follow-ups: SHORT sweep_reversal DEVELOPING"


def test_portfolio_summary_is_empty_for_legacy_analysis() -> None:
    analysis = SimpleNamespace(opportunity_portfolio=None)

    assert decision_analysis._portfolio_summary_lines(analysis) == ()
