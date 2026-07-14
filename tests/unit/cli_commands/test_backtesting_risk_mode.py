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
