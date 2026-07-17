"""Public optimization API."""

from apex.optimization.adapters import (
    performance_from_futures_historical_payload,
    performance_from_spot_historical_payload,
)
from apex.optimization.contracts import (
    CalibrationEvaluation,
    CalibrationStage,
    CandidateParameterSet,
    OptimizationDecision,
    OptimizationGroup,
    OptimizationResult,
    OptimizationRunConfig,
    PerformanceSummary,
    WalkForwardSplit,
)
from apex.optimization.empirical import (
    S10_EMPIRICAL_REPORT_SCHEMA_VERSION,
    EmpiricalCalibrationReport,
    StabilityPolicy,
    build_empirical_calibration_report,
    load_and_verify_empirical_calibration_report,
    write_empirical_calibration_report,
)
from apex.optimization.engine import (
    calibration_to_payload,
    compare_backtest_studies,
    compare_performance,
    evaluate_performance,
    evaluate_walk_forward_calibration,
    load_performance_report,
    performance_from_backtest_study,
    performance_from_campaign_payload,
    performance_from_mapping,
    result_to_payload,
    save_optimization_result,
)

__all__ = [
    "S10_EMPIRICAL_REPORT_SCHEMA_VERSION",
    "CalibrationEvaluation",
    "CalibrationStage",
    "CandidateParameterSet",
    "EmpiricalCalibrationReport",
    "OptimizationDecision",
    "OptimizationGroup",
    "OptimizationResult",
    "OptimizationRunConfig",
    "PerformanceSummary",
    "StabilityPolicy",
    "WalkForwardSplit",
    "build_empirical_calibration_report",
    "calibration_to_payload",
    "compare_backtest_studies",
    "compare_performance",
    "evaluate_performance",
    "evaluate_walk_forward_calibration",
    "load_and_verify_empirical_calibration_report",
    "load_performance_report",
    "performance_from_backtest_study",
    "performance_from_campaign_payload",
    "performance_from_futures_historical_payload",
    "performance_from_mapping",
    "performance_from_spot_historical_payload",
    "result_to_payload",
    "save_optimization_result",
    "write_empirical_calibration_report",
]
