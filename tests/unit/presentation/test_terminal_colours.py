from __future__ import annotations

import typer

from apex.presentation.terminal import _emit_setup_header


def _capture_secho(
    monkeypatch,
) -> list[tuple[str, str | None, bool, bool]]:
    calls: list[tuple[str, str | None, bool, bool]] = []

    def record(
        message: object = "",
        *,
        fg: str | None = None,
        bold: bool = False,
        nl: bool = True,
        **_: object,
    ) -> None:
        calls.append((str(message), fg, bold, nl))

    monkeypatch.setattr(typer, "secho", record)
    return calls


def test_setup_header_colours_symbol_yellow_and_long_green(monkeypatch) -> None:
    calls = _capture_secho(monkeypatch)

    rendered = _emit_setup_header(
        "┌─ SETUP PLAN 2 • AKE/USDT • LONG • Momentum breakout ─────────"
    )

    assert rendered is True
    assert ("AKE/USDT", typer.colors.BRIGHT_YELLOW, True, False) in calls
    assert ("LONG", typer.colors.BRIGHT_GREEN, True, False) in calls


def test_setup_header_colours_short_red(monkeypatch) -> None:
    calls = _capture_secho(monkeypatch)

    rendered = _emit_setup_header(
        "┌─ SETUP PLAN 1 • O/USDT • SHORT • Trend pullback ─────────────"
    )

    assert rendered is True
    assert ("O/USDT", typer.colors.BRIGHT_YELLOW, True, False) in calls
    assert ("SHORT", typer.colors.BRIGHT_RED, True, False) in calls


def test_non_trade_section_header_is_not_claimed(monkeypatch) -> None:
    _capture_secho(monkeypatch)

    assert _emit_setup_header("┌─ SCAN SUMMARY ─────────────────────────") is False
