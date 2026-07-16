"""Tests for the futures product configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from apex.config import FuturesProductConfig, RiskModeDefaults, load_futures_product_config
from apex.domain import RiskMode


def _defaults() -> RiskModeDefaults:
    return RiskModeDefaults(
        account_loss_percentage=0.25,
        minimum_leverage=1,
        preferred_leverage=2,
        maximum_leverage=5,
        maximum_wallet_exposure_percentage=15,
        maximum_open_risk_percentage=0.75,
        maximum_daily_loss_percentage=1,
        maximum_consecutive_losses=2,
    )


def test_default_futures_configuration_loads() -> None:
    config = load_futures_product_config(Path("config/futures.yaml"))

    assert config.futures_only is True
    assert config.default_risk_mode is RiskMode.STANDARD
    assert config.defaults_for(RiskMode.STANDARD).preferred_leverage == 2
    assert config.defaults_for(RiskMode.STANDARD).minimum_leverage == 1
    assert config.execution_costs.total_cost_fraction > 0


def test_standard_risk_mode_is_required() -> None:
    with pytest.raises(
        ValidationError,
        match="missing risk-mode configuration: STANDARD",
    ):
        FuturesProductConfig(risk_modes={})


def test_invalid_leverage_order_is_rejected() -> None:
    with pytest.raises(ValidationError, match="minimum <= preferred <= maximum"):
        RiskModeDefaults(
            account_loss_percentage=1,
            minimum_leverage=1,
            preferred_leverage=12,
            maximum_leverage=10,
            maximum_wallet_exposure_percentage=20,
            maximum_open_risk_percentage=2,
            maximum_daily_loss_percentage=3,
            maximum_consecutive_losses=4,
        )


def test_minimum_leverage_cannot_exceed_one() -> None:
    with pytest.raises(ValidationError):
        RiskModeDefaults(
            account_loss_percentage=1,
            minimum_leverage=2,
            preferred_leverage=2,
            maximum_leverage=5,
            maximum_wallet_exposure_percentage=20,
            maximum_open_risk_percentage=2,
            maximum_daily_loss_percentage=3,
            maximum_consecutive_losses=4,
        )
