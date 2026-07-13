"""Public Phase 9 paper-trading API."""

from apex.paper_trading.contracts import (
    TERMINAL_STATES,
    BacktestPaperComparison,
    PaperPerformance,
    PaperReport,
    PaperTrade,
    PaperTradeConfig,
    PaperTradeState,
)
from apex.paper_trading.engine import (
    build_paper_replay_report,
    compare_backtest_to_paper,
    create_paper_trade,
    generate_paper_report,
    paper_lifecycle_snapshot,
    summarize_paper_trades,
    update_paper_trade,
)
from apex.paper_trading.store import PaperTradeStore

__all__ = [
    "TERMINAL_STATES",
    "BacktestPaperComparison",
    "PaperPerformance",
    "PaperReport",
    "PaperTrade",
    "PaperTradeConfig",
    "PaperTradeState",
    "PaperTradeStore",
    "build_paper_replay_report",
    "compare_backtest_to_paper",
    "create_paper_trade",
    "generate_paper_report",
    "paper_lifecycle_snapshot",
    "summarize_paper_trades",
    "update_paper_trade",
]
