"""Public market-intelligence API."""

from apex.intelligence.analysis import (
    calculate_symbol_correlation,
    correlation_matrix,
    disabled_intelligence_metadata,
    intelligence_metadata,
    summarize_market_risk,
)
from apex.intelligence.contracts import (
    FundingRateSnapshot,
    MarketWideRiskSummary,
    OpenInterestSnapshot,
    SymbolCorrelation,
)

__all__ = [
    "FundingRateSnapshot",
    "MarketWideRiskSummary",
    "OpenInterestSnapshot",
    "SymbolCorrelation",
    "calculate_symbol_correlation",
    "correlation_matrix",
    "disabled_intelligence_metadata",
    "intelligence_metadata",
    "summarize_market_risk",
]
