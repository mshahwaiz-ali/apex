"""Focused public application API for Apex trade discovery.

Only services required by the active CLI surface are re-exported here.
"""

from apex.application.analysis_records import (
    build_analysis_record,
    write_analysis_record,
    write_analysis_record_sqlite,
)
from apex.application.bootstrap import bootstrap
from apex.application.configuration_identity import configuration_metadata
from apex.application.discovery_contracts import ScanResult
from apex.application.decision_analysis import (
    SymbolAnalysis,
    analyze_symbol,
    scan_symbols,
    write_json_report,
)
from apex.application.futures_scan_selection import (
    FuturesScanSelection,
    select_futures_scan_symbols,
    serialize_futures_screening,
)
from apex.application.market_data import create_market_data_services
from apex.application.outcome_evaluation import ManualOutcome, append_manual_outcome
from apex.application.public_output import serialize_scan_result, serialize_symbol_analysis
from apex.application.selected_symbol import analyze_selected_symbol
from apex.application.symbols import load_symbol_file, normalize_market_symbol

__all__ = [
    "FuturesScanSelection",
    "ManualOutcome",
    "ScanResult",
    "SymbolAnalysis",
    "analyze_selected_symbol",
    "analyze_symbol",
    "append_manual_outcome",
    "bootstrap",
    "build_analysis_record",
    "configuration_metadata",
    "create_market_data_services",
    "load_symbol_file",
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
