"""Resolve validated futures account inputs for CLI and future runtimes."""

from __future__ import annotations

from pathlib import Path

from apex.config import FuturesProductConfig, load_futures_product_config
from apex.domain import FuturesAccountInput, LeverageMode, RiskMode

DEFAULT_FUTURES_CONFIG_PATH = Path("config/futures.yaml")


def build_futures_account_input(
    *,
    wallet_balance: float,
    risk_mode: RiskMode | str | None = None,
    leverage_mode: Le