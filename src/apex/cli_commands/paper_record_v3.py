"""Risk-mode aligned paper record command."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import cast

import typer

from apex.application import (
    bootstrap,
    build_futures_plan_result,
    create_market_data_services,
    load_default_risk_config,
    normalize_market_symbol,
    serialize_symbol_analysis,
)
from apex.application.account_context import resolve_account_context
from apex.application.analysis import analyze_symbol
from apex.application.exposure_classification import classify_proposed_exposure
from apex.application.futures_risk_mode import futures_risk_mode_scope
from apex.application.paper_account_state import (
    PaperAccountExposure,
    attach_account_state_registration,
)
from apex.data.providers.errors import MarketDataProviderError
from apex.paper_trading import (
    PaperTradeStore,
    create_paper_trade,
    derive_paper_trade_guidance,
)
