"""Deterministic market-structure engine."""

from apex.structure.analysis import analyze_structure
from apex.structure.breaks import detect_changes_of_character, detect_structure_breaks
from apex.structure.contracts import (
    BreakDirection,
    BreakQuality,
    ChangeOfCharacter,
    ComparisonPolicy,
    ConfirmationStatus,
    LevelRole,
    LevelStatus,
    PivotStatus,
    RangeBreakoutState,
    RangeStructure,
    StructureAnalysisResult,
    StructureBreak,
    StructureEvidenceSummary,
    StructureLevel,
    SwingPoint,
    SwingType,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
)
from apex.structure.levels import derive_structure_levels
from apex.structure.ranges import detect_range
from apex.structure.regime import (
    MarketRegime,
    RangeBoundary,
    RangeBoundarySide,
    TrendStrength,
    classify_market_regime,
    range_boundaries,
    trend_strength_band,
)
from apex.structure.registry import StructureRegistry, create_default_structure_registry
from apex.structure.swings import detect_swings
from apex.structure.trend import classify_trend

__all__ = [
    "BreakDirection",
    "BreakQuality",
    "ChangeOfCharacter",
    "ComparisonPolicy",
    "ConfirmationStatus",
    "LevelRole",
    "LevelStatus",
    "MarketRegime",
    "PivotStatus",
    "RangeBoundary",
    "RangeBoundarySide",
    "RangeBreakoutState",
    "RangeStructure",
    "StructureAnalysisResult",
    "StructureBreak",
    "StructureEvidenceSummary",
    "StructureLevel",
    "StructureRegistry",
    "SwingPoint",
    "SwingType",
    "TrendAnalysis",
    "TrendDirection",
    "TrendEvidence",
    "TrendStrength",
    "analyze_structure",
    "classify_market_regime",
    "classify_trend",
    "create_default_structure_registry",
    "derive_structure_levels",
    "detect_changes_of_character",
    "detect_range",
    "detect_structure_breaks",
    "detect_swings",
    "range_boundaries",
    "trend_strength_band",
]
