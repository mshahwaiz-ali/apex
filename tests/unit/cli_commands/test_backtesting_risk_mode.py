from apex.application.futures_risk_mode import (
    current_futures_risk_mode,
    futures_risk_mode_scope,
)
from apex.domain import RiskMode


def test_futures_risk_mode_scope_accepts_standard_and_restores_mode() -> None:
    assert current_futures_risk_mode() is RiskMode.STANDARD

    with futures_risk_mode_scope('standard'):
        assert current_futures_risk_mode() is RiskMode.STANDARD

    assert current_futures_risk_mode() is RiskMode.STANDARD


def test_phase6_risk_configuration_matches_standard_mode() -> None:
    from apex.risk import RiskConfig, resolve_risk_config_for_mode

    standard = resolve_risk_config_for_mode(RiskConfig(), RiskMode.STANDARD)

    assert standard.identifier == 'phase6-standard-v2'
    assert standard.risk_per_trade_pct == 0.25
