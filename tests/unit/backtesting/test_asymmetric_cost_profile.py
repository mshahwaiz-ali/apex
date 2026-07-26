from __future__ import annotations

from apex.backtesting.contracts import BacktestConfig


def test_backtest_cost_profile_preserves_asymmetric_entry_and_exit_values() -> None:
    config = BacktestConfig(
        entry_fee_pct=0.02,
        exit_fee_pct=0.05,
        entry_slippage_pct=0.0,
        exit_slippage_pct=0.02,
        cost_profile="conservative_market",
    )

    assert config.effective_entry_fee_pct == 0.02
    assert config.effective_exit_fee_pct == 0.05
    assert config.effective_entry_slippage_pct == 0.0
    assert config.effective_exit_slippage_pct == 0.02
