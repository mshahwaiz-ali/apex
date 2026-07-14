"""Public long-only spot portfolio backtesting API."""

from apex.spot_backtesting.contracts import (
    SpotBacktestConfig,
    SpotBacktestResult,
    SpotBar,
    SpotEntryLeg,
    SpotEquityPoint,
    SpotExitReason,
    SpotMarketRegime,
    SpotOrderPlan,
    SpotPortfolioMetrics,
    SpotPosition,
    SpotTarget,
    SpotTradeRecord,
)
from apex.spot_backtesting.engine import run_spot_backtest
from apex.spot_backtesting.metrics import compute_spot_portfolio_metrics

__all__ = [
    "SpotBacktestConfig",
    "SpotBacktestResult",
    "SpotBar",
    "SpotEntryLeg",
    "SpotEquityPoint",
    "SpotExitReason",
    "SpotMarketRegime",
    "SpotOrderPlan",
    "SpotPortfolioMetrics",
    "SpotPosition",
    "SpotTarget",
    "SpotTradeRecord",
    "compute_spot_portfolio_metrics",
    "run_spot_backtest",
]
