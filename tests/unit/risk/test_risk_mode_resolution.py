import pytest

from apex.domain import RiskMode
from apex.risk import RiskConfig, RiskProfile, resolve_risk_config_for_mode


def test_resolve_standard_risk_config_uses_canonical_futures_limits() -> None:
    base = RiskConfig(
        identifier='fixture-base',
        account_equity=12_500.0,
        minimum_risk_reward=1.75,
        minimum_stop_distance_pct=0.20,
        minimum_stop_atr_multiple=1.25,
        maximum_stop_distance_pct=2.5,
        structural_stop_buffer_pct=0.07,
        maximum_entry_chase_pct=0.30,
    )

    resolved = resolve_risk_config_for_mode(base, RiskMode.STANDARD)

    assert resolved.identifier == 'phase6-standard-v2'
    assert resolved.profile is RiskProfile.CONTROLLED
    assert resolved.risk_per_trade_pct == pytest.approx(0.25)
    assert resolved.maximum_leverage == pytest.approx(5.0)
    assert resolved.account_equity == pytest.approx(12_500.0)
    assert resolved.minimum_risk_reward == pytest.approx(1.75)
    assert resolved.minimum_stop_distance_pct == pytest.approx(0.20)
    assert resolved.minimum_stop_atr_multiple == pytest.approx(1.25)
    assert resolved.maximum_stop_distance_pct == pytest.approx(2.5)
    assert resolved.structural_stop_buffer_pct == pytest.approx(0.07)
    assert resolved.maximum_entry_chase_pct == pytest.approx(0.30)
    assert resolved.maximum_open_risk_pct >= resolved.risk_per_trade_pct


def test_resolve_risk_config_for_mode_accepts_case_insensitive_standard() -> None:
    resolved = resolve_risk_config_for_mode(RiskConfig(), 'standard')

    assert resolved.identifier == 'phase6-standard-v2'
    assert resolved.profile is RiskProfile.CONTROLLED
    assert resolved.risk_per_trade_pct == pytest.approx(0.25)


def test_resolved_mode_includes_canonical_execution_costs() -> None:
    resolved = resolve_risk_config_for_mode(RiskConfig(), RiskMode.STANDARD)

    assert resolved.entry_fee_pct == pytest.approx(0.04)
    assert resolved.exit_fee_pct == pytest.approx(0.04)
    assert resolved.entry_slippage_pct == pytest.approx(0.03)
    assert resolved.exit_slippage_pct == pytest.approx(0.03)
