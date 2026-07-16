"""Tests for canonical Phase-6 risk configuration resolution."""

from pathlib import Path

import pytest

from apex.risk import RiskProfile, load_risk_config


def test_standard_risk_config_resolves_canonical_limits() -> None:
    config = load_risk_config(Path("config/risk.yaml"))

    assert config.profile is RiskProfile.CONTROLLED
    assert config.risk_per_trade_pct == 0.25
    assert config.maximum_leverage == 5.0
    assert config.maintenance_margin_pct == 0.5
    assert config.maximum_open_risk_pct == 0.75
    assert config.maximum_daily_loss_pct == 1.0
    assert config.maximum_consecutive_losses == 2


def test_obsolete_aggressive_profile_is_rejected(tmp_path: Path) -> None:
    risk_path = tmp_path / "risk.yaml"
    risk_path.write_text("profile: aggressive\n", encoding="utf-8")

    with pytest.raises(ValueError, match="aggressive"):
        load_risk_config(risk_path)


def test_duplicate_canonical_field_is_rejected(tmp_path: Path) -> None:
    risk_path = tmp_path / "risk.yaml"
    risk_path.write_text(
        "profile: controlled\nmaximum_leverage: 20.0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicates canonical"):
        load_risk_config(risk_path)
