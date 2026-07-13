"""Tests for the Phase 1 futures product configuration."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from apex.config import FuturesProductConfig, RiskModeDefaults, load_futures_product_config
from apex.domain import RiskMode


def test_default_futures_configuration_loads() -> None:
    config = load_futures_product_config(Path("config/futures.yaml"))

    assert config.futures_only is True
    assert config.default_risk_mode is RiskMode.AGGRESSIVE
    assert config.defaults_for(RiskMode.AGGRESSIVE).preferred_leverage == 18


def test_all_risk_modes_are_required() -> None:
    defaults = RiskModeDefaults(
        account_loss_percentage=1,
        minimum_leverage=10,
        preferred_leverage=12,
        maximum_leverage=15,
        maximum_wallet_exposure_percentage=20,
    )

    with pytest.raises(ValidationError, match="missing risk-mode configuration"):
        FuturesProductConfig(risk_modes={RiskMode.STANDARD: defaults})


def test_invalid_leverage_order_is_rejected() -> None:
    with pytest.raises(ValidationError, match="minimum <= preferred <= maximum"):
        RiskModeDefaults(
            account_loss_percentage=1,
            minimum_leverage=15,
            preferred_leverage=12,
            maximum_leverage=10,
            maximum_wallet_exposure_percentage=20,
        )
