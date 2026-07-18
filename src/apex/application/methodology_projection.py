"""Project existing discovery setups into canonical methodology snapshots."""

from __future__ import annotations

from dataclasses import replace

from apex.application.discovery_contracts import DiscoverySetup, SymbolAnalysis
from apex.application.market_state import MarketStateSnapshot
from apex.application.market_usability import (
    MarketUs