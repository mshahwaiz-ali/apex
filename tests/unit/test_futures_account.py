"""Tests for CLI-facing futures account input resolution."""

import pytest
from pydantic import ValidationError

from apex.application import build_futures_account_input
from apex.domain import LeverageMode, RiskMode


def test_defaults_resolve_from_product_configuration() -> None:
    account = build_futures_account_input(wallet_balance=100)

    assert account.risk_mode is RiskMode.AGGRESSIVE
    assert account.leverage_mode is LeverageMode.AUTOMATIC
    assert account.maximum_account_loss_percentage == 2.5
    assert account.maximum_account_loss_amount == 2.5


def test_case_insensitive_cli_values_are_supported() -> None:
    account = build_futures_account_input(
        wallet_balance=250,
        risk_mode="standard",
        leverage_mode="manual",
        manual_leverage=12,
    )

    assert account.risk_mode is RiskMode.STANDARD
    assert account.leverage_mode is LeverageMode.MANUAL
    assert account.manual_leverage == 12
    assert account.maximum_account_loss_percentage == 1.0


def test_explicit_loss_override_is_preserved() -> None:
    account = build_futures_account_input(
        wallet_balance=200,
        maximum_account_loss_percentage=4,
    )

    assert account.maximum_account_loss_amount == 8


def test_manual_leverage_is_rejected_in_automatic_mode() -> None:
    with pytest.raises(ValidationError, match="manual leverage must be omitted"):
        build_futures_account_input(
            wallet_balance=100,
            leverage_mode="automatic",
            manual_leverage=20,
        )
