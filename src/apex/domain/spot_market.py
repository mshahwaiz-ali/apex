"""Provider-independent spot market metadata, scanner, and eligibility contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SpotScannerMode(StrEnum):
    ELIGIBLE = "eligible"
    WATCHLIST = "watchlist"
    ALL = "all"


class SpotEligibilityReason(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    INSUFFICIENT_QUOTE_VOLUME = "INSUFFICIENT_QUOTE_VOLUME"
    INSUFFICIENT_MARKET_HISTORY = "INSUFFICIENT