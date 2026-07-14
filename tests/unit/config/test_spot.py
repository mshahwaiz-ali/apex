from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from apex.config import SpotProductConfig, load_spot_product_config


def test_default_spot_configuration_loads() -> None:
    config = load_spot_product_config(Path("config/spot.yaml"))

    assert config.spot_only is True
    assert config.long_only is True
    assert config.leverage_allowed is False
    assert config.borrowed_assets_allowed is False
    assert config.primary_timeframes == ("1w", "1d", "12h", "4h")
    assert config.forbidden_thesis_timeframes == ("1m", "3m", "5m")
    assert config.allocation.maximum_open_positions == 4
    assert sum(config.entry.default_entry_allocations) == 100.0
    assert sum(config.exit.default_target_allocations) == 100.0


def test_spot_configuration_rejects_leverage() -> None:
    base = load_spot_product_config(Path("config/spot.yaml")).model_dump(mode="python")
    base["leverage_allowed"] = True

    with pytest.raises(ValidationError, match="cannot enable leverage"):
        SpotProductConfig.model_validate(base)


def test_spot_configuration_rejects_borrowed_assets() -> None:
    base = load_spot_product_config(Path("config/spot.yaml")).model_dump(mode="python")
    base["borrowed_assets_allowed"] = True

    with pytest.raises(ValidationError, match="cannot enable borrowed assets"):
        SpotProductConfig.model_validate(base)


def test_spot_configuration_rejects_lower_timeframe_thesis() -> None:
    base = load_spot_product_config(Path("config/spot.yaml")).model_dump(mode="python")
    base["primary_timeframes"] = ("1d", "4h", "5m")

    with pytest.raises(ValidationError, match="cannot influence the spot thesis"):
        SpotProductConfig.model_validate(base)


def test_spot_configuration_rejects_reserve_exposure_conflict() -> None:
    base = load_spot_product_config(Path("config/spot.yaml")).model_dump(mode="python")
    base["allocation"]["maximum_total_spot_exposure_percentage"] = 80.0
    base["allocation"]["minimum_quote_reserve_percentage"] = 30.0

    with pytest.raises(ValidationError, match="cannot exceed 100 percent"):
        SpotProductConfig.model_validate(base)
