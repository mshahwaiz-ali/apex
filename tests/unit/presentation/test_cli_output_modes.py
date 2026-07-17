"""Tests for the active CLI output-mode surface."""

from __future__ import annotations

import pytest

from apex.presentation import OutputMode, normalize_cli_output_mode


def test_cli_output_mode_accepts_text_and_json() -> None:
    assert normalize_cli_output_mode("text") is OutputMode.TEXT
    assert normalize_cli_output_mode(" JSON ") is OutputMode.JSON


@pytest.mark.parametrize("value", ("verbose", "debug", "yaml", "html"))
def test_cli_output_mode_rejects_non_primary_modes(value: str) -> None:
    with pytest.raises(
        ValueError,
        match="CLI output mode must be one of: text, json",
    ):
        normalize_cli_output_mode(value)
