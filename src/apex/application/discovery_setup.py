"""Build discovery-neutral trade plans from selected candidates."""

from __future__ import annotations

from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoveryAssessment,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    StopQualityBand,
    TakeProfit,
)
from apex.application.opportunity_portfolio import (
    AnalysisMode,
    SymbolOpportunityPortfolio,
   