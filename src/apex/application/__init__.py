"""Application public API."""

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
from apex.application.bootstrap import ApplicationContext, bootstrap
from apex.application.chronological_backtest import (
    ChronologicalBacktestRequest,
    ChronologicalBacktestResult,
    run_chronological_pipeline_backtest,
)
from apex.application.futures_account import (
    DEFAULT_FUTURES_CONFIG_PATH,
    build_futures_account_input,
)
from apex.application.futures_plan import (
    FuturesPlanSafetyError,
    build_futures_plan,
    build_futures_plan_result,
)
from apex.application.market_data import MarketDataServices, create_market_data_services
from apex.application.precision_entry import build_precision_entry_plan
from apex.application.selected_symbol import analyze_selected_symbol
from apex.application.symbols import DEFAULT_QUOTE_ASSETS, normalize_market_symbol

__all__ = [
    "ANALYSIS_RECORD_DB_SCHEMA_VERSION",
    "ANALYSIS_RECORD_SCHEMA_VERSION",
    "BACKTEST_CAMPAIGN_DB_SCHEMA_VERSION",
    "BACKTEST_CAMPAIGN_SCHEMA_VERSION",
    "BACKTEST_REPORT_DB_SCHEMA_VERSION",
    "DEFAULT_FUTURES_CONFIG_PATH",
    "DEFAULT_QUOTE_ASSETS",
    "ApplicationContext",
    "BacktestCampaignRequest",
    "BacktestCampaignResult",
    "BacktestCampaignRun",
    "BacktestCampaignVariant",
    "ChronologicalBacktestRequest",
    "ChronologicalBacktestResult",
    "FuturesPlanSafetyError",
    "MarketDataServices",
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
    "campaign_result_to_payload",
    "create_market_data_services",
    "default_campaign_variants",
    "format_scan_text",
    "format_symbol_text",
    "list_analysis_record_metadata_sqlite",
    "list_backtest_campaign_metadata_sqlite",
    "list_backtest_report_metadata_sqlite",
    "load_analysis_record_sqlite",
    "load_backtest_campaign_sqlite",
    "load_backtest_report_sqlite",
    "load_default_risk_config",
    "load_symbols",
    "normalize_market_symbol",
    "parse_campaign_variants",
    "run_backtest_campaign",
    "run_chronological_pipeline_backtest",
    "run_multi_symbol_backtest_campaign",
    "scan_symbols",
    "serialize_scan_result",
    "serialize_symbol_analysis",
    "split_campaign_candles_by_symbol",
    "write_analysis_record",
    "write_analysis_record_sqlite",
    "write_backtest_campaign_sqlite",
    "write_backtest_report_sqlite",
    "write_json_report",
]
