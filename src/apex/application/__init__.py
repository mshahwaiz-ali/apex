"""Stable public API used by the Apex command-line layer.

Keep this facade intentionally small. Importing optional application subsystems here can
create cycles because lower-level backtesting and paper-trading modules import focused
application modules directly.
"""

from apex.application.account_state import AccountStateSnapshot, AccountStateStore
from apex.application.analysis_records import (
    build_analysis_record,
    list_analysis_record_metadata_sqlite,
    load_analysis_record_sqlite,
    write_analysis_record,
    write_analysis_record_sqlite,
)
from apex.application.backtest_campaign import (
    BacktestCampaignRequest,
    MultiSymbolBacktestCampaignRequest,
    campaign_result_to_payload,
    parse_campaign_variants,
    run_backtest_campaign,
    run_multi_symbol_backtest_campaign,
    split_campaign_candles_by_symbol,
)
from apex.application.baseline_campaign_plan import BaselineCampaignPlan, BaselineDatasetRef
from apex.application.bootstrap import bootstrap
from apex.application.chronological_backtest import (
    ChronologicalBacktestRequest,
    run_chronological_pipeline_backtest,
)
from apex.application.decision_analysis import (
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
from apex.application.futures_account import build_futures_account_input
from apex.application.futures_scan_selection import (
    FuturesScanSelection,
    select_futures_scan_symbols,
    serialize_futures_screening,
)
from apex.application.futures_symbol_resolution import resolve_futures_symbols
from apex.application.market_data import create_market_data_services
from apex.application.precision_entry import build_precision_entry_plan
from apex.application.risk_approval import (
    FuturesPlanSafetyError,
    build_futures_plan,
    build_futures_plan_result,
)
from apex.application.selected_symbol import analyze_selected_symbol
from apex.application.spot_account import build_spot_account_input
from apex.application.symbols import normalize_market_symbol
from apex.application.trade_management_reporting import format_trade_management_plan

__all__ = [
    "AccountStateSnapshot",
    "AccountStateStore",
    "BacktestCampaignRequest",
    "BaselineCampaignPlan",
    "BaselineDatasetRef",
    "ChronologicalBacktestRequest",
    "FuturesPlanSafetyError",
    "FuturesScanSelection",
    "MultiSymbolBacktestCampaignRequest",
    "ScanResult",
    "SymbolAnalysis",
    "analyze_selected_symbol",
    "analyze_symbol",
    "bootstrap",
    "build_analysis_record",
    "build_futures_account_input",
    "build_futures_plan",
    "build_futures_plan_result",
    "build_precision_entry_plan",
    "build_spot_account_input",
    "campaign_result_to_payload",
    "create_market_data_services",
    "format_scan_text",
    "format_symbol_text",
    "format_trade_management_plan",
    "list_analysis_record_metadata_sqlite",
    "load_analysis_record_sqlite",
    "load_default_risk_config",
    "load_symbols",
    "normalize_market_symbol",
    "parse_campaign_variants",
    "run_backtest_campaign",
    "run_chronological_pipeline_backtest",
    "resolve_futures_symbols",
    "run_multi_symbol_backtest_campaign",
    "scan_symbols",
    "select_futures_scan_symbols",
    "serialize_futures_screening",
    "serialize_scan_result",
    "serialize_symbol_analysis",
    "split_campaign_candles_by_symbol",
    "write_analysis_record",
    "write_analysis_record_sqlite",
    "write_json_report",
]
