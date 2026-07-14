"""Resolve validated spot account inputs for CLI and future runtimes."""

from __future__ import annotations

from pathlib import Path

from apex.config import SpotProductConfig, load_spot_product_config
from apex.domain import SpotAccountInput, SpotBalanceInput

DEFAULT_SPOT_CONFIG_PATH = Path("config/spot.yaml")


def build_spot_account_input(
    *,
    quote_asset: str,
    available_quote_balance: float,
    total_spot_equity: float,
    current_sp