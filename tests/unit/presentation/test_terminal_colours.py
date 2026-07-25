from __future__ import annotations

import typer

from apex.presentation.terminal import _emit_setup_header, _emit_target_line


def _capture_terminal_calls(
    monkeypatch,
) -> tuple[
    list[tuple[str, str | None, bool, bool]],
    list[tuple[str, bool]],
]:
    secho_calls: list[tuple[str, str | None, bool, bool]] = []
    echo_calls: list[tuple[str, bool]] = []

    def record_secho(
        message: object = "",
        *,
        fg: str | None = None,
        bold: bool = False,
        nl: bool = True,
        **_: object,
    ) -> None:
        secho_calls.append((str(message), fg, bold, nl))

    def record_echo(
        message: object = "",
        *,
        nl: bool = True,
        **_: object,
    ) -> None:
        echo_calls.append((str(message), nl))

    monkeypatch.setattr(typer, "secho", record_secho)
    monkeypatch.setattr(typer, "echo", record_echo)
    return secho_calls, echo_calls


def test_setup_header_colours_plan_cyan_symbol_yellow_and_long_green(monkeypatch) -> None:
    calls, _ = _capture_terminal_calls(monkeypatch)

    rendered = _emit_setup_header(
        "┌─ SETUP PLAN 2 • RE-ENTRY • AKE/USDT • LONG • Momentum breakout ─────────"
    )

    assert rendered is True
    assert ("SETUP PLAN 2 • RE-ENTRY", typer.colors.BRIGHT_CYAN, True, False) in calls
    assert ("AKE/USDT", typer.colors.BRIGHT_YELLOW, True, False) in calls
    assert ("LONG", typer.colors.BRIGHT_GREEN, True, False) in calls


def test_setup_header_colours_short_red(monkeypatch) -> None:
    calls, _ = _capture_terminal_calls(monkeypatch)

    rendered = _emit_setup_header(
        "┌─ SETUP PLAN 1 • O/USDT • SHORT • Trend pullback ─────────────"
    )

    assert rendered is True
    assert ("O/USDT", typer.colors.BRIGHT_YELLOW, True, False) in calls
    assert ("SHORT", typer.colors.BRIGHT_RED, True, False) in calls


def test_target_line_colours_only_price_and_percentage(monkeypatch) -> None:
    secho_calls, echo_calls = _capture_terminal_calls(monkeypatch)

    rendered = _emit_target_line(
        "  TP1  0.1237  -1.40%  • front-run of 1h opposing support zone"
    )

    assert rendered is True
    assert ("  TP1  ", False) in echo_calls
    assert ("0.1237  -1.40%", typer.colors.BRIGHT_GREEN, False, False) in secho_calls
    assert ("  • front-run of 1h opposing support zone", True) in echo_calls


def test_non_trade_section_header_is_not_claimed(monkeypatch) -> None:
    _capture_terminal_calls(monkeypatch)

    assert _emit_setup_header("┌─ SCAN SUMMARY ─────────────────────────") is False
