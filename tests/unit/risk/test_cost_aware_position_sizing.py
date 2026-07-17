import pytest

from apex.risk.config import RiskConfig
from apex.risk.contracts import ActionableEntry, StopLoss
from apex.risk.engine import _position_size


def test_risk_analysis_position_size_reserves_cap_for_execution_costs() -> None:
    config = RiskConfig(
        account_equity=10_000.0,
        risk_per_trade_pct=0.75,
        maximum_open_risk_pct=0.75,
        maximum_directional_risk_pct=30.0,
        maximum_correlated_risk_pct=20.0,
        entry_fee_pct=0.04,
        exit_fee_pct=0.04,
        entry_slippage_pct=0.03,
        exit_slippage_pct=0.03,
    )
    entry = ActionableEntry(
        lower=99.5,
        upper=100.5,
        preferred=100.0,
        current_price=100.0,
        maximum_chase_price=101.0,
        current_price_inside_zone=True,
    )
    stop = StopLoss(
        price=99.9,
        distance=0.1,
        distance_pct=0.1,
        rationale=("fixture stop",),
    )

    position = _position_size(config, entry, stop)

    structural_loss = position.notional_value * 0.001
    modeled_costs = position.notional_value * 0.0014

    assert position.risk_amount == pytest.approx(75.0)
    assert structural_loss + modeled_costs == pytest.approx(75.0)
    assert position.notional_value == pytest.approx(31_250.0)
    assert position.quantity == pytest.approx(312.5)
    assert position.required_leverage == pytest.approx(3.125)


def test_risk_analysis_execution_costs_reduce_gross_only_notional() -> None:
    config = RiskConfig(
        account_equity=10_000.0,
        risk_per_trade_pct=0.75,
        maximum_open_risk_pct=0.75,
        maximum_directional_risk_pct=30.0,
        maximum_correlated_risk_pct=20.0,
        entry_fee_pct=0.04,
        exit_fee_pct=0.04,
        entry_slippage_pct=0.03,
        exit_slippage_pct=0.03,
    )
    entry = ActionableEntry(
        lower=99.5,
        upper=100.5,
        preferred=100.0,
        current_price=100.0,
        maximum_chase_price=101.0,
        current_price_inside_zone=True,
    )
    stop = StopLoss(
        price=99.9,
        distance=0.1,
        distance_pct=0.1,
        rationale=("fixture stop",),
    )

    position = _position_size(config, entry, stop)

    gross_only_notional = 75.0 / 0.001

    assert position.notional_value < gross_only_notional
    assert position.required_leverage < 10.0
