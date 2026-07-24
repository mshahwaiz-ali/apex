"""TTY-aware terminal presentation helpers for Apex CLI commands."""

from __future__ import annotations

import itertools
import sys
import threading
from contextlib import AbstractContextManager
from types import TracebackType
from typing import TextIO

import typer

_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


class CliProgress(AbstractContextManager["CliProgress"]):
    """Render transient stage feedback to stderr when stderr is interactive."""

    def __init__(
        self,
        *,
        stream: TextIO | None = None,
        refresh_seconds: float = 0.08,
    ) -> None:
        self._stream = stream if stream is not None else sys.stderr
        self._refresh_seconds = refresh_seconds
        self._enabled = bool(getattr(self._stream, "isatty", lambda: False)())
        self._stage = ""
        self._last_width = 0
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        """Return whether transient progress output is active."""

        return self._enabled

    def __enter__(self) -> CliProgress:
        if self._enabled:
            self._thread = threading.Thread(
                target=self._animate,
                name="apex-cli-progress",
                daemon=True,
            )
            self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def update(self, stage: str) -> None:
        """Replace the currently displayed stage without emitting a permanent line."""

        if not self._enabled:
            return
        with self._lock:
            self._stage = stage.strip()

    def close(self) -> None:
        """Stop animation and remove any transient terminal content."""

        if not self._enabled:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self._refresh_seconds * 4, 0.2))
        with self._lock:
            self._clear_line()
        self._enabled = False

    def _animate(self) -> None:
        for frame in itertools.cycle(_SPINNER_FRAMES):
            if self._stop.wait(self._refresh_seconds):
                return
            with self._lock:
                if self._stage:
                    self._draw(frame, self._stage)

    def _draw(self, frame: str, stage: str) -> None:
        plain_text = f"{frame} {stage}"
        colored_frame = typer.style(frame, fg=typer.colors.BRIGHT_CYAN)
        padding = " " * max(self._last_width - len(plain_text), 0)
        self._stream.write(f"\r{colored_frame} {stage}{padding}")
        self._stream.flush()
        self._last_width = len(plain_text)

    def _clear_line(self) -> None:
        if self._last_width:
            self._stream.write(f"\r{' ' * self._last_width}\r")
            self._stream.flush()
            self._last_width = 0


def cli_progress(*, stream: TextIO | None = None) -> CliProgress:
    """Create shared, TTY-aware CLI progress feedback."""

    return CliProgress(stream=stream)


def emit_terminal(text: str) -> None:
    """Print reports with a restrained semantic terminal palette."""

    for line in text.splitlines():
        stripped = line.lstrip()
        upper = stripped.upper()
        if line.startswith(("╭", "╰")):
            typer.secho(line, fg=typer.colors.BRIGHT_CYAN, bold=True)
        elif line.startswith("┌─"):
            typer.secho(line, fg=typer.colors.CYAN, bold=True)
        elif line.startswith("└"):
            typer.secho(line, fg=typer.colors.CYAN)
        elif "• LONG •" in line or line.rstrip().endswith("— LONG"):
            typer.secho(line, fg=typer.colors.BRIGHT_GREEN, bold=True)
        elif "• SHORT •" in line or line.rstrip().endswith("— SHORT"):
            typer.secho(line, fg=typer.colors.BRIGHT_RED, bold=True)
        elif line.startswith("▶"):
            typer.secho(line, fg=typer.colors.BRIGHT_WHITE, bold=True)
        elif stripped in {"ENTRY", "RISK", "TARGETS", "SETUP", "WHY THIS TRADE", "WARNINGS"}:
            typer.secho(line, fg=typer.colors.BRIGHT_WHITE, bold=True)
        elif stripped.startswith(("Stop loss ", "Invalidation ", "Pre-entry invalidation ")):
            typer.secho(line, fg=typer.colors.BRIGHT_RED)
        elif stripped.startswith(("TP1 ", "TP2 ", "TP3 ")):
            typer.secho(line, fg=typer.colors.BRIGHT_GREEN)
        elif upper.startswith(("CRITICAL ", "ERROR ", "INVALIDATED ")):
            typer.secho(line, fg=typer.colors.BRIGHT_RED, bold=True)
        elif upper.startswith(("WARNING ", "MEDIUM ", "CAUTION ")) or line.startswith("!"):
            typer.secho(line, fg=typer.colors.YELLOW, bold=True)
        else:
            typer.echo(line)


__all__ = ["CliProgress", "cli_progress", "emit_terminal"]
