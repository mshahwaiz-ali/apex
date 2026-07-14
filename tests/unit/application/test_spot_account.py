from __future__ import annotations

import pytest

from apex.application import build_spot_account_input
from apex.config import load_spot_product_config
from apex.domain import SpotBalanceInput


def test_spot_account_resolver_normalizes_quote_asset() -> None:
    account = build_spot_account_input(
        quote_asset="usdt",
        available_quote_balance=750.0,
        total_spot_equity=1000.0,
        current_spot_exposure=250.0,
        open_position_count=1,
        balances=(SpotBalanceInput(asset="BTC", available=0.01),),
    )

    assert account.quote_asset == "USDT"
    assert account.current_spot_exposure == 250.0


def test_spot_account_resolver_enforces_configured_position_limit() -> None:
    config = load_spot_product_config("config/spot.yaml")

    with pytest.raises(ValueError, match="exceeds configured maximum"):
        build_spot_account_input(
            quote_asset="USDT",
            available_quote_balance=1000.0,
            total_spot_equity=1000.0,
            open_position_count=config.allocation.maximum_open_positions + 1,
            config=config,
        )
