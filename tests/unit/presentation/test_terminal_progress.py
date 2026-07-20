"""Tests for shared interactive CLI progress rendering."""

from __future__ import annotations

import time
from io import StringIO

import pytest

from apex.presentation.terminal import CliProgress


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
