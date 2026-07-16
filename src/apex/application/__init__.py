"""Application public API."""

from apex.application.account_state import (
    ACCOUNT_STATE_SCHEMA_VERSION,
    AccountStateSnapshot,
    AccountStateStore,
)
from apex.application.analysis import (
    ScanResult,
    SymbolAnalysis,
    analyze_symbol,
    format_scan_text,
    format_symbol_text,
    load_default_risk_config,
    load_symbols,
    scan_symbols,
    serialize_scan_result,
    serialize_symbol_analysis,
    write_json_report,
)
from apex.application.analysis_records import (
    ANALYSIS_RECORD_DB_SCHEMA_VERSION,
    ANALYSIS_RECORD_SCHEMA_VERSION,
    build_analysis_record,
    list_analysis_record_metadata_sqlite,
    load_analysis_record_sqlite,
    write_analysis_record,
    write_analysis_record_sqlite,
)
from apex.application.backtest_campaign import (
    BACKTEST_CAMPAIGN_SCHEMA_VERSION,
    BacktestCampaignRequest,
    BacktestCampaignResult,
    BacktestCampaignRun,
    BacktestCampaignVariant,
    MultiSymbolBacktestCampaignRequest,
    campaign_result_to_payload,
    default_campaign_variants,
    parse_campaign_variants,
    run_backtest_campaign,
    run_multi_symbol_backtest_campaign,
    split_campaign_candles_by_symbol,
)
from apex.application.backtest_report_io import (
    BACKTEST_CAMPAIGN_DB_SCHEMA_VERSION,
    BACKTEST_REPORT_DB_SCHEMA_VERSION,
    list_backtest_campaign_metadata_sqlite,
    list_backtest_report_metadata_sqlite,
    load_backtest_campaign_sqlite,
    load_backtest_report_sqlite,
    write_backtest_campaign_sqlite,
    write_backtest_report_sqlite,
)
from apex.application.baseline_campaign_plan import (
    BASELINE_CAMPAIGN_PLAN_SCHEMA_VERSION,
    BaselineCampaignManifest,
    BaselineCampaignPlan,
    BaselineDatasetRef,
)
from apex.application.bootstrap import ApplicationContext, bootstrap
from apex.application.chronological_backtest import (
    ChronologicalBacktestRequest,
    ChronologicalBacktestResult,
    run_chronological_pipeline_backtest,
)
from apex.application.funded_futures_plan import build_funded_futures_plan_result
from apex.application.futures_account import (
    DEFAULT_FUTURES_CONFIG_PATH,
    build_futures_account_input,
)
from apex.application.futures_quality import (
    DEFAULT_STRATEGY_APPROVAL_CONFIG_PATH,
    analyze_futures_phase5,
)
from apex.application.historical_signal_generation import (
    HistoricalSignalGenerationResult,
    HistoricalSignalRecord,
    build_historical_signal_record,
    generate_historical_signals,
)
from apex.application.historical_signal_io import (
    HISTORICAL_SIGNAL_EXECUTION_SCHEMA_VERSION,
    HistoricalSignalExecutionManifest,
    hash_configuration_files,
    hash_historical_signal_records,
    load_historical_signal_execution_manifest,
    load_historical_signal_record_payloads,
    write_historical_signal_generation,
)
from apex.application.market_data import MarketDataServices, create_market_data_services
from apex.application.paper_lifecycle_analytics import (
    HoldingTimeBand,
    PaperLifecycleAnalytics,
    PaperLifecycleTradeRecord,
    RiskMultipleBand,
    build_paper_lifecycle_analytics,
    paper_lifecycle_analytics_payload,
)
from apex.application.precision_entry import build_precision_entry_plan
from apex.application.risk_approval import (
    FuturesPlanSafetyError,
    StrategyApprovalError,
    build_futures_plan,
    build_futures_plan_result,
)
from apex.application.selected_symbol import analyze_selected_symbol
from apex.application.spot_account import DEFAULT_SPOT_CONFIG_PATH, build_spot_account_input
from apex.application.spot_analysis import (
    SPOT_ANALYSIS_SCHEMA_VERSION,
    SpotAnalysisRequest,
    SpotAnalysisResult,
    analyze_spot_request,
    spot_analysis_result_to_payload,
)
from apex.application.spot_analysis_io import (
    DEFAULT_SPOT_STRATEGY_CONFIG_PATH,
    SpotAnalysisInput,
    analyze_spot_from_files,
    analyze_spot_from_input,
    load_spot_analysis_input,
    write_spot_analysis_result,
)
from apex.application.spot_entry_eligibility import (
    SpotEntryEligibilityResult,
    evaluate_spot_entry_eligibility,
)
from apex.application.spot_lifecycle import (
    SpotLifecycleEvent,
    SpotLifecycleEventType,
    replay_spot_lifecycle,
)
from apex.application.spot_orchestration import (
    SpotOrchestrationInput,
    SpotSetupEvidence,
    analyze_spot_orchestration,
    build_spot_strategy_input,
)
from apex.application.spot_orchestration_io import (
    analyze_spot_orchestration_from_files,
    analyze_spot_orchestration_input,
    load_spot_orchestration_input,
    write_spot_orchestration_result,
)
from apex.application.spot_planning import SpotPlanningRequest, SpotPlanningResult, build_spot_plan
from apex.application.spot_strategies import (
    evaluate_accumulation_range_breakout,
    evaluate_breakout_retest,
    evaluate_higher_timeframe_trend_pullback,
    evaluate_liquidity_sweep_daily_recovery,
    evaluate_post_capitulation_recovery,
    evaluate_relative_strength_leader_pullback,
    evaluate_spot_strategies,
)
from apex.application.spot_structure import (
    analyze_spot_structure,
    classify_spot_market_regime,
    classify_spot_timeframe,
)
from apex.application.symbols import DEFAULT_QUOTE_ASSETS, normalize_market_symbol
from apex.application.trade_management import build_trade_management_plan
from apex.application.trade_management_reporting import format_trade_management_plan

__all__ = [name for name in globals() if not name.startswith("_")]
