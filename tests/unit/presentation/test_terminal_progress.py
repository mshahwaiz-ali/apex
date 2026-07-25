"""Tests for shared interactive CLI progress rendering."""

from __future__ import annotations

import time
from io import StringIO

import pytest
import typer

from apex.presentation.terminal import CliProgress, emit_terminal


class _TTYStream(StringIO):
    def isatty(self) -> bool:
        return True


class _NonTTYStream(StringIO):
    def isatty(self) -> bool:
        return False


def test_progress_renders_stage_to_interactive_stderr_and_clears() -> None:
    stream = _TTYStream()
    stage = "Running multi-timeframe analysis…"

    with CliProgress(stream=stream, refresh_seconds=0.001) as progress:
        progress.update(stage)
        time.sleep(0.01)

    rendered = stream.getvalue()
    assert stage in rendered
    assert typer.style("⠋", fg=typer.colors.BRIGHT_CYAN) in rendered
    assert rendered.endswith("\r")
    assert "\n" not in rendered
    assert f"\r{' ' * (len(stage) + 2)}\r" in rendered


def test_progress_is_quiet_for_non_tty_stream() -> None:
    stream = _NonTTYStream()

    with CliProgress(stream=stream, refresh_seconds=0.001) as progress:
        progress.update("Preparing output…")

    assert stream.getvalue() == ""


def test_progress_clears_when_command_body_raises() -> None:
    stream = _TTYStream()
    stage = "Fetching BTCUSDT market data…"

    with (
        pytest.raises(RuntimeError, match="provider failed"),
        CliProgress(stream=stream, refresh_seconds=0.001) as progress,
    ):
        progress.update(stage)
        time.sleep(0.01)
        raise RuntimeError("provider failed")

    rendered = stream.getvalue()
    assert stage in rendered
    assert rendered.endswith("\r")
    assert "\n" not in rendered
    assert f"\r{' ' * (len(stage) + 2)}\r" in rendered


def test_opportunity_headers_color_long_green_and_short_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str | None, bool]] = []

    def capture(line: str, *, fg: str | None = None, bold: bool = False) -> None:
        calls.append((line, fg, bold))

    monkeypatch.setattr(typer, "secho", capture)
    monkeypatch.setattr(typer, "echo", lambda line, **kwargs: None)

    emit_terminal("▶  #1  BTCUSDT — LONG\n▶  #2  ETHUSDT — SHORT")

    assert calls == [
        ("▶  #1  BTCUSDT — LONG", typer.colors.BRIGHT_GREEN, True),
        ("▶  #2  ETHUSDT — SHORT", typer.colors.BRIGHT_RED, True),
    ]


def test_terminal_uses_professional_trade_geometry_colors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str | None, bool]] = []

    def capture(line: str, *, fg: str | None = None, bold: bool = False) -> None:
        calls.append((line, fg, bold))

    monkeypatch.setattr(typer, "secho", capture)
    monkeypatch.setattr(typer, "echo", lambda line, **kwargs: None)

    emit_terminal(
        "  ENTRY\n    Ideal entry  100\n  RISK\n    Stop loss  97\n  TARGETS\n    TP1  106"
    )

    assert calls == [
        ("  ENTRY", typer.colors.BRIGHT_CYAN, True),
        ("  RISK", typer.colors.BRIGHT_CYAN, True),
        ("    Stop loss  97", typer.colors.BRIGHT_RED, False),
        ("  TARGETS", typer.colors.BRIGHT_CYAN, True),
        ("    TP1  106", typer.colors.BRIGHT_GREEN, False),
    ]


def test_terminal_colors_cmp_scores_r_and_warning_severity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str | None, bool]] = []

    def capture(line: str, *, fg: str | None = None, bold: bool = False) -> None:
        calls.append((line, fg, bold))

    monkeypatch.setattr(typer, "secho", capture)
    monkeypatch.setattr(typer, "echo", lambda line, **kwargs: None)

    emit_terminal(
        "  CMP                0.3045\n"
        "  Setup quality      44.1/100\n"
        "  Execution quality  20.0/100\n"
        "  Target quality     79.0/100\n"
        "  Gross / net R      0.41R net\n"
        "    - active-candle evidence is provisional\n"
        "    - no post-confirmation execution room"
    )

    assert calls == [
        ("0.3045", typer.colors.BRIGHT_YELLOW, True),
        ("44.1/100", typer.colors.BRIGHT_RED, True),
        ("20.0/100", typer.colors.BRIGHT_RED, True),
        ("79.0/100", typer.colors.BRIGHT_GREEN, True),
        ("0.41R net", typer.colors.BRIGHT_RED, True),
        ("    - active-candle evidence is provisional", typer.colors.YELLOW, True),
        ("    - no post-confirmation execution room", typer.colors.BRIGHT_RED, True),
    ]
