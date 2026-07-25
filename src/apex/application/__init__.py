"""Focused public application API for Apex trade discovery.

Only services required by the active CLI surface are re-exported here.
"""

from apex.application.analysis_records import (
    reconcile_pending_opportunities_sqlite,
    write_analysis_record,
    write_analysis_record_sqlite,
)
from apex.application.bootstrap import bootstrap
from apex.application.canonical_scan import scan_symbols
from apex.application.configuration_identity import configuration_metadata
from apex.application.decision_analysis import (
    SymbolAnalysis,
    analyze_symbol,
    write_json_report,
)
from apex.application.discovery_contracts import ScanResult
from apex.application.enriched_public_output import (
    serialize_scan_result,
    serialize_symbol_analysis,
)
from apex.application.futures_scan_selection import (
    FuturesScanSelection,
    select_futures_scan_symbols,
    serialize_futures_screening,
)
from apex.application.market_data import create_market_data_services
from apex.application.methodology_analysis_records import build_analysis_record
from apex.application.outcome_evaluation import ManualOutcome, append_manual_outcome
from apex.application.rollout_acceptance import (
    RolloutAcceptanceResult,
    evaluate_rollout_acceptance,
    rollout_acceptance_payload,
)
from apex.application.rollout_comparison import (
    AnalysisComparisonReport,
    DiagnosticDifference,
    analysis_comparison_payload,
    compare_analysis_outputs,
)
from apex.application.rollout_reporting import (
    RolloutCommand,
    build_rollout_operator_report,
    write_rollout_operator_report,
)
from apex.application.selected_symbol import analyze_selected_symbol
from apex.application.symbols import load_symbol_file, normalize_market_symbol

__all__ = [
    "AnalysisComparisonReport",
    "DiagnosticDifference",
    "FuturesScanSelection",
    "ManualOutcome",
    "RolloutAcceptanceResult",
    "RolloutCommand",
    "ScanResult",
    "SymbolAnalysis",
    "analysis_comparison_payload",
    "analyze_selected_symbol",
    "analyze_symbol",
    "append_manual_outcome",
    "bootstrap",
    "build_analysis_record",
    "build_rollout_operator_report",
    "compare_analysis_outputs",
    "configuration_metadata",
    "create_market_data_services",
    "evaluate_rollout_acceptance",
    "load_symbol_file",
    "normalize_market_symbol",
    "reconcile_pending_opportunities_sqlite",
    "rollout_acceptance_payload",
    "scan_symbols",
    "select_futures_scan_symbols",
    "serialize_futures_screening",
    "serialize_scan_result",
    "serialize_symbol_analysis",
    "write_analysis_record",
    "write_analysis_record_sqlite",
    "write_json_report",
    "write_rollout_operator_report",
]
