"""Public Phase 9 and P1 paper-trading API."""

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
)
from apex.paper_trading.forward_edge_contracts import (
    ForwardPaperEdgeProfile,
    ForwardPaperValidationPolicy,
    ForwardPaperValidationReason,
    ForwardPaperValidationResult,
    ForwardPaperValidationStatus,
)
from apex.paper_trading.forward_edge_evaluation import (
    build_forward_paper_edge_profile,
    evaluate_forward_paper_edge,
)
from apex.paper_trading.forward_validation import (
    FORWARD_PAPER_DAILY_REPORT_SCHEMA_VERSION,
    ForwardPaperDailyReport,
    build_forward_paper_daily_report,
    load_and_verify_forward_paper_daily_report,
    write_forward_paper_daily_report,
)
from apex.paper_trading.guidance import (
    PaperTradeGuidance,
    build_paper_guidance_report,
    derive_paper_trade_guidance,
)
from apex.paper_trading.management import (
    advance_paper_trade,
    expire_waiting_trade,
    paper_entry_expiry,
)
from apex.paper_trading.store import PaperTradeStore

update_paper_trade = advance_paper_trade

__all__ = [
    "FORWARD_PAPER_DAILY_REPORT_SCHEMA_VERSION",
    "TERMINAL_STATES",
    "BacktestPaperComparison",
    "ForwardPaperDailyReport",
    "ForwardPaperEdgeProfile",
    "ForwardPaperValidationPolicy",
    "ForwardPaperValidationReason",
    "ForwardPaperValidationResult",
    "ForwardPaperValidationStatus",
    "PaperPerformance",
    "PaperReport",
    "PaperTrade",
    "PaperTradeConfig",
    "PaperTradeGuidance",
    "PaperTradeState",
    "PaperTradeStore",
    "advance_paper_trade",
    "build_forward_paper_daily_report",
    "build_forward_paper_edge_profile",
    "build_paper_guidance_report",
    "build_paper_replay_report",
    "compare_backtest_to_paper",
    "create_paper_trade",
    "derive_paper_trade_guidance",
    "evaluate_forward_paper_edge",
    "expire_waiting_trade",
    "generate_paper_report",
    "load_and_verify_forward_paper_daily_report",
    "paper_entry_expiry",
    "paper_lifecycle_snapshot",
    "summarize_paper_trades",
    "update_paper_trade",
    "write_forward_paper_daily_report",
]
