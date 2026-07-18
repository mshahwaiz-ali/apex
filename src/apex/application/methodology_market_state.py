"""Adapt existing fused market-state output to methodology taxonomy."""

from __future__ import annotations

from apex.application.market_state import (
    MarketStateDirection,
    MarketStateSnapshot,
    MarketStateTag,
)
from apex.application.methodology_strategy_contracts import (
    MarketStateClassification,
    PrimaryMarketState,
    SecondaryMarketCondition,
)


_PRIMARY_BY_TAG_AND_DIRECTION: dict[
    tuple[Market