"""Focused public application API for Apex trade discovery.

Only services required by the active CLI surface are re-exported here. Legacy
account, execution, paper-trading, campaign, funded-readiness, and spot modules
remain internal until they are removed or redesigned.
"""

from apex.application.analysis_records import (
    build_analysis_record,
    write_analysis_record,
    write_analysis_record_sqlite,
)
from apex.application.bootstrap import bootstrap
from apex.application.decision_analysis import (
    ScanResult,
    SymbolAnalysis,
    analyze_symbol,
    scan_symbols,
    serialize_scan_result,
    serialize_symbol_analysis,
    write_json_report,
)
from apex.application.futures_scan_selection import (
    FuturesScanSelection,
    select_futures_scan_symbols,
    serialize_futures_screening,
)
from apex.application.market_data import create_market_data_services
from apex.application.selected_symbol import analyze_selected_symbol
from apex.application.symbols import normalize_market_symbol

__all__ = [
    "FuturesScanSelection",
    "ScanResult",
    "SymbolAnalysis",
    "analyze_selected_symbol",
    "analyze_symbol",
    "bootstrap",
    "build_analysis_record",
    "create_market_data_services",
    "normalize_market_symbol",
    "scan_symbols",
    "select_futures_scan_symbols",
    "serialize_futures_screening",
    "serialize_scan_result",
    "serialize_symbol_analysis",
    "write_analysis_record",
    "write_analysis_record_sqlite",
    "write_json_report",
]
