from apex.application.discovery_contracts import ActionableEntry, StopLoss, TakeProfit
from apex.application.discovery_setup import _clamp_entry_opportunities_to_net_r
from apex.strategies.contracts import TradeDirection


def test_all_long_entry_opportunities_receive_the_same_net_r_chase_policy() -> None:
    entries = (
        ActionableEntry(99.0, 100.0, 99.5, 99.5, 104.0, True),
        ActionableEntry(97.0, 98.0, 97.5, 99.5, 103.0, False),
    )
    stop = StopLoss(95.0, 4.5, 4.5, ("structure",))
    tp1 = TakeProfit("TP1", 105.0, 5.5, 1.22, ("structure",))

    clamped = _clamp_entry_opportunities_to_net_r(
        entries,
        direction=TradeDirection.LONG,
        stop=stop,
        tp1=tp1,
        minimum_net_r=1.25,
        expected_cost_pct=0.06,
    )

    assert len(clamped) == 2
    assert clamped[0].maximum_chase_price < entries[0].maximum_chase_price
    assert clamped[1].maximum_chase_price < entries[1].maximum_chase_price
    assert clamped[0].maximum_chase_price >= clamped[0].upper
    assert clamped[1].maximum_chase_price >= clamped[1].upper


def test_all_short_entry_opportunities_receive_the_same_net_r_chase_policy() -> None:
    entries = (
        ActionableEntry(100.0, 101.0, 100.5, 100.5, 96.0, True),
        ActionableEntry(102.0, 103.0, 102.5, 100.5, 97.0, False),
    )
    stop = StopLoss(105.0, 4.5, 4.5, ("structure",))
    tp1 = TakeProfit("TP1", 95.0, 5.5, 1.22, ("structure",))

    clamped = _clamp_entry_opportunities_to_net_r(
        entries,
        direction=TradeDirection.SHORT,
        stop=stop,
        tp1=tp1,
        minimum_net_r=1.25,
        expected_cost_pct=0.06,
    )

    assert len(clamped) == 2
    assert clamped[0].maximum_chase_price > entries[0].maximum_chase_price
    assert clamped[1].maximum_chase_price > entries[1].maximum_chase_price
    assert clamped[0].maximum_chase_price <= clamped[0].lower
    assert clamped[1].maximum_chase_price <= clamped[1].lower
