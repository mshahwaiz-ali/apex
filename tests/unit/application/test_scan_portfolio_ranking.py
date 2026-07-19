from __future__ import annotations

from types import SimpleNamespace

from apex.application import decision_analysis


def _analysis(
    *,
    current_long: object | None = None,
    current_short: object | None = None,
    nearby_long: object | None = None,
    nearby_short: object | None = None,
    follow_ups: tuple[object, ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        opportunity_portfolio=SimpleNamespace(
            current_long=current_long,
            current_short=current_short,
            nearby_long=nearby_long,
            nearby_short=nearby_short,
            follow_up_opportunities=follow_ups,
        ),
        assessment=SimpleNamespace(setup=None, developing_setup=None),
    )


def test_current_secondary_direction_ranks_as_actionable() -> None:
    analysis = _analysis(current_short=object())

    assert decision_analysis._scan_maturity_class(analysis) == 0


def test_nearby_slot_ranks_as_developing() -> None:
    analysis = _analysis(nearby_long=object())

    assert decision_analysis._scan_maturity_class(analysis) == 1


def test_empty_portfolio_ranks_as_no_trade() -> None:
    analysis = _analysis()

    assert decision_analysis._scan_maturity_class(analysis) == 3


def test_portfolio_maturity_takes_precedence_over_legacy_assessment() -> None:
    analysis = _analysis(current_long=object())

    assert decision_analysis._scan_maturity_class(analysis) == 0
