"""Regression coverage for immutable backtest report JSON serialization."""

from __future__ import annotations

import json
from types import MappingProxyType

from apex.application.backtest_report_io import dumps_report, to_json_value
from apex.backtesting import BacktestReport


def test_backtest_report_with_mappingproxy_is_json_safe() -> None:
    report = BacktestReport(
        trades=(),
        total_trades=0,
        win_rate=0.0,
        loss_rate=0.0,
        breakeven_rate=0.0,
        gross_profit=0.0,
        gross_loss=0.0,
        net_profit=0.0,
        profit_factor=None,
        average_win=0.0,
        average_loss=0.0,
        average_risk_reward=0.0,
        expectancy=0.0,
        maximum_drawdown=0.0,
        consecutive_wins=0,
        consecutive_losses=0,
        by_symbol={},
        by_strategy={},
        metadata={"dataset": "forward-paper"},
    )

    assert isinstance(report.metadata, MappingProxyType)

    payload = to_json_value(report)

    assert payload["metadata"] == {"dataset": "forward-paper"}
    assert payload["trades"] == []
    assert json.loads(dumps_report(report)) == payload
