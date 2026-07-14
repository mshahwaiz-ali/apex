import pytest

from apex.domain import RiskMode
from apex.risk import (
    RiskConfig,
    RiskProfile,
    resolve_risk_config_for_mode,
)


@pytest.mark.parametrize(
    (
        "risk_mode",
        "expected_identifier",
        "expected_profile",
        "expected_risk_pct",
        "expected_maximum_leverage",
    ),
    (
        (
            RiskMode.STANDARD,
            "phase6-standard-v2",
            RiskProfile.CONTROLLED,
            0.25,
            5.0,
        ),
        (
            RiskMode.AGGRESSIVE,
            "phase6-aggressive-v2",
            RiskProfile.AGGRESSIVE,
            0.75,
            10.0,
        ),
        (
            RiskMode.EXTREME,
            "phase6-extreme-v2",
            RiskProfile.EXTREME,
            2.0,
            20.0,
        ),
    ),
)
def test_resolve_risk_config_for_mode_uses_canonical_futures_limits(
    risk_mode: RiskMode,
    expected_identifier: str,
    expected_profile: RiskProfile,
    expected_risk_pct: float,
    expected_maximum_leverage: float,
) -> None:
    base = RiskConfig(
        identifier="fixture-base",
        account_equity=12_500.0,
        minimum_risk_reward=1.75,
        minimum_stop_distance_pct=0.20,
        minimum_stop_atr_multiple=1.25,
        maximum_stop_distance_pct=2.5,
        structural_stop_buffer_pct=0.07,
        maximum_entry_chase_pct=0.30,
    )

    resolved = resolve_risk_config_for_mode(base, risk_mode)

    assert resolved.identifier == expected_identifier
    assert resolved.profile is expected_profile
    assert resolved.risk_per_trade_pct == pytest.approx(expected_risk_pct)
    assert resolved.maximum_leverage == pytest.approx(expected_maximum_leverage)

    assert resolved.account_equity == pytest.approx(12_500.0)
    assert resolved.minimum_risk_reward == pytest.approx(1.75)
    assert resolved.minimum_stop_distance_pct == pytest.approx(0.20)
    assert resolved.minimum_stop_atr_multiple == pytest.approx(1.25)
    assert resolved.maximum_stop_distance_pct == pytest.approx(2.5)
    assert resolved.structural_stop_buffer_pct == pytest.approx(0.07)
    assert resolved.maximum_entry_chase_pct == pytest.approx(0.30)

    assert resolved.maximum_open_risk_pct >= resolved.risk_per_trade_pct


def test_resolve_risk_config_for_mode_accepts_case_insensitive_string() -> None:
    resolved = resolve_risk_config_for_mode(
        RiskConfig(),
        "aggressive",
    )

    assert resolved.identifier == "phase6-aggressive-v2"
    assert resolved.profile is RiskProfile.AGGRESSIVE
    assert resolved.risk_per_trade_pct == pytest.approx(0.75)


def test_resolved_mode_includes_canonical_execution_costs() -> None:
    resolved = resolve_risk_config_for_mode(
        RiskConfig(),
        RiskMode.AGGRESSIVE,
    )

    assert resolved.entry_fee_pct == pytest.approx(0.04)
    assert resolved.exit_fee_pct == pytest.approx(0.04)
    assert resolved.entry_slippage_pct == pytest.approx(0.03)
    assert resolved.exit_slippage_pct == pytest.approx(0.03)
