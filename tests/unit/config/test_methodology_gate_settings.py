from __future__ import annotations

import pytest

from apex.config import FileSettings


def test_methodology_gate_defaults_to_shadow() -> None:
    settings = FileSettings()

    assert settings.methodology_gate_mode == "shadow"


def test_methodology_gate_accepts_explicit_enforcement() -> None:
    settings = FileSettings(methodology_gate_mode="enforce")

    assert settings.methodology_gate_mode == "enforce"


def test_methodology_gate_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError):
        FileSettings.model_validate({"methodology_gate_mode": "disabled"})
