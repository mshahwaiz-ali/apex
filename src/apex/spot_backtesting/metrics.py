"""Portfolio-level metrics for deterministic spot backtests."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence

from apex.spot_backtesting.contracts import (
    SpotEquityPoint,
    SpotPortfolioMetrics,
    SpotTradeRecord,
)


def compute_spot_portfolio_metrics(
    trades: Sequence[SpotTradeRecord],
    equity_curve: Sequence[SpotEquityPoint],
    *,
    starting_cash: float,
) -> SpotPortfolioMetrics:
