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
    leverage_mode: LeverageMode | str | None = None,
    manual_leverage: float | None = None,
    maximum_account_loss_percentage: float | None = None,
    config: FuturesProductConfig | None = None,
    config_path: str | Path = DEFAULT_FUTURES_CONFIG_PATH,
) -> FuturesAccountInput:
    """Build account inputs using validated product defaults where omitted."""

    product = config or load_futures_product_config(config_path)
    selected_risk_mode = (
        product.default_risk_mode if risk_mode is None else RiskMode(str(risk_mode).upper())
    )
    selected_leverage_mode = (
        product.default_leverage_mode
        if leverage_mode is None
        else LeverageMode(str(leverage_mode).upper())
    )
    defaults = product.defaults_for(selected_risk_mode)
    selected_loss_percentage = (
        defaults.account_loss_percentage
        if maximum_account_loss_percentage is None
        else maximum_account_loss_percentage
    )

    return FuturesAccountInput(
        wallet_balance=wallet_balance,
        leverage_mode=selected_leverage_mode,
        manual_leverage=manual_leverage,
        risk_mode=selected_risk_mode,
        maximum_account_loss_percentage=selected_loss_percentage,
        margin_mode=product.margin_mode,
    )
