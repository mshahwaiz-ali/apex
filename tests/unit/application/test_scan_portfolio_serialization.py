from __future__ import annotations

from types import SimpleNamespace

from apex.application import decision_analysis


def test_scan_opportunity_records_preserve_portfolio_order() -> None:
    opportunities = (
        SimpleNamespace(
            opportunity_id="long-1",
            sequence_role=SimpleNamespace(value="current"),
            setup=SimpleNamespace(
                direction=SimpleNamespace(value="long"),
                strategy=SimpleNamespace(value="breakout_continuation"),
                entry_status=SimpleNamespace(value="READY_NOW"),
                execution_allowed_now=True,
            ),
        ),
        SimpleNamespace(
            opportunity_id="short-1",
            sequence_role=SimpleNamespace(value="current"),
            setup=SimpleNamespace(
                direction=SimpleNamespace(value="short"),
                strategy=SimpleNamespace(value="breakout_continuation"),
                entry_status=SimpleNamespace(value="READY_NOW"),
                execution_allowed_now=True,
            ),
        ),
    )
    analysis = SimpleNamespace(
        symbol="BTC/USDT",
        opportunity_portfolio=SimpleNamespace(all_opportunities=opportunities),
    )

    records = decision_analysis._scan_opportunity_records((analysis,))

    assert [item["opportunity_id"] for item in records] == ["long-1", "short-1"]
    assert [item["direction"] for item in records] == ["long", "short"]
