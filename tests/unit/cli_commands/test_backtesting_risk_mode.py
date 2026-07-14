from apex.application.futures_risk_mode import (
    current_futures_risk_mode,
    futures_risk_mode_scope,
)
from apex.domain import RiskMode


def test_futures_risk_mode_scope_changes_and_restores_mode() -> None:
    assert current_futures_risk_mode() is RiskMode.STANDARD

    with futures_risk_mode_scope(RiskMode.AGGRESSIVE):
        assert current_futures_risk_mode() is RiskMode.AGGRESSIVE

    assert current_futures_risk_mode() is RiskMode.STANDARD


def test_phase6_risk_configuration_matches_selected_futures_mode() -> None:
    from apex.risk import RiskConfig, resolve_risk_config_for_mode

    standard = resolve_risk_config_for_mode(
        RiskConfig(),
        RiskMode.STANDARD,
    )
    aggressive = resolve_risk_config_for_mode(
        RiskConfig(),
        RiskMode.AGGRESSIVE,
    )
    extreme = resolve_risk_config_for_mode(
        RiskConfig(),
        RiskMode.EXTREME,
    )

    assert standard.identifier == "phase6-standard-v2"
    assert standard.risk_per_trade_pct == 0.25

    assert aggressive.identifier == "phase6-aggressive-v2"
    assert aggressive.risk_per_trade_pct == 0.75

    assert extreme.identifier == "phase6-extreme-v2"
    assert extreme.risk_per_trade_pct == 2.0
