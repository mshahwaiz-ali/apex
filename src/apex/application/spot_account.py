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
    current_spot_exposure: float = 0.0,
    open_position_count: int = 0,
    balances: tuple[SpotBalanceInput, ...] = (),
    config: SpotProductConfig | None = None,
    config_path: str | Path = DEFAULT_SPOT_CONFIG_PATH,
) -> SpotAccountInput:
    """Build a spot account snapshot without futures-only account semantics."""

    product = config or load_spot_product_config(config_path)
    if open_position_count > product.allocation.maximum_open_positions:
        raise ValueError("open spot position count exceeds configured maximum")

    return SpotAccountInput(
        quote_asset=quote_asset.upper(),
        available_quote_balance=available_quote_balance,
        total_spot_equity=total_spot_equity,
        current_spot_exposure=current_spot_exposure,
        open_position_count=open_position_count,
        balances=balances,
    )
