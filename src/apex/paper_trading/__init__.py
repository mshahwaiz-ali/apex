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
from apex.paper_trading.forward_review import (
    FORWARD_PAPER_REVIEW_SCHEMA_VERSION,
    DeviationCompatibilityStatus,
    ForwardDeviationPolicy,
    ForwardDeviationReport,
    ForwardPaperReviewReport,
    LifecycleAnomaly,
    LifecycleAnomalyCode,
    LifecycleAuditReport,
    P1ReviewState,
    audit_paper_trade_lifecycle,
    build_forward_paper_review_report,
    compare_historical_to_forward,
    load_and_verify_forward_paper_review_report,
    write_forward_paper_review_report,
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
from apex.paper_trading.intake import (
    IntakeCandidate,
    IntakeMarketType,
    IntakeReason,
    IntakeResult,
    IntakeStatus,
    IntakeSummary,
    build_futures_intake_candidate,
    build_spot_intake_candidate,
    intake_summary_payload,
    persist_intake_candidates,
)
from apex.paper_trading.management import (
    advance_paper_trade,
    expire_waiting_trade,
    paper_entry_expiry,
)
from apex.paper_trading.operations import (
    PaperOperationCycleResult,
    run_paper_operation_cycle,
    write_paper_operation_cycle_result,
)
from apex.paper_trading.operations_status import (
    MarketOperationsStatus,
    PaperOperationsStatus,
    build_paper_operations_status,
)
from apex.paper_trading.runtime import (
    CandleProvider,
    PaperRuntimeResult,
    run_provider_backed_paper_cycle,
)
from apex.paper_trading.scheduler import (
    PaperCycleAlreadyRunningError,
    ScheduledPaperCycleResult,
    append_scheduled_paper_cycle_log,
    paper_cycle_lock,
    run_scheduled_paper_cycle,
)
from apex.paper_trading.store import PaperTradeStore

update_paper_trade = advance_paper_trade

__all__ = [
    "FORWARD_PAPER_DAILY_REPORT_SCHEMA_VERSION",
    "FORWARD_PAPER_REVIEW_SCHEMA_VERSION",
    "TERMINAL_STATES",
    "BacktestPaperComparison",
    "CandleProvider",
    "DeviationCompatibilityStatus",
    "ForwardDeviationPolicy",
    "ForwardDeviationReport",
    "ForwardPaperDailyReport",
    "ForwardPaperEdgeProfile",
    "ForwardPaperReviewReport",
    "ForwardPaperValidationPolicy",
    "ForwardPaperValidationReason",
    "ForwardPaperValidationResult",
    "ForwardPaperValidationStatus",
    "IntakeCandidate",
    "IntakeMarketType",
    "IntakeReason",
    "IntakeResult",
    "IntakeStatus",
    "IntakeSummary",
    "LifecycleAnomaly",
    "LifecycleAnomalyCode",
    "LifecycleAuditReport",
    "MarketOperationsStatus",
    "P1ReviewState",
    "PaperCycleAlreadyRunningError",
    "PaperOperationCycleResult",
    "PaperOperationsStatus",
    "PaperPerformance",
    "PaperReport",
    "PaperRuntimeResult",
    "PaperTrade",
    "PaperTradeConfig",
    "PaperTradeGuidance",
    "PaperTradeState",
    "PaperTradeStore",
    "ScheduledPaperCycleResult",
    "advance_paper_trade",
    "append_scheduled_paper_cycle_log",
    "audit_paper_trade_lifecycle",
    "build_forward_paper_daily_report",
    "build_forward_paper_edge_profile",
    "build_forward_paper_review_report",
    "build_futures_intake_candidate",
    "build_paper_guidance_report",
    "build_paper_operations_status",
    "build_paper_replay_report",
    "build_spot_intake_candidate",
    "compare_backtest_to_paper",
    "compare_historical_to_forward",
    "create_paper_trade",
    "derive_paper_trade_guidance",
    "evaluate_forward_paper_edge",
    "expire_waiting_trade",
    "generate_paper_report",
    "intake_summary_payload",
    "load_and_verify_forward_paper_daily_report",
    "load_and_verify_forward_paper_review_report",
    "paper_cycle_lock",
    "paper_entry_expiry",
    "paper_lifecycle_snapshot",
    "persist_intake_candidates",
    "run_paper_operation_cycle",
    "run_provider_backed_paper_cycle",
    "run_scheduled_paper_cycle",
    "summarize_paper_trades",
    "update_paper_trade",
    "write_forward_paper_daily_report",
    "write_forward_paper_review_report",
    "write_paper_operation_cycle_result",
]
