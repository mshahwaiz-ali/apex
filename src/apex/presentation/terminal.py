"""TTY-aware terminal presentation helpers for Apex CLI commands."""

from __future__ import annotations

import itertools
import re
import sys
import threading
from contextlib import AbstractContextManager
from types import TracebackType
from typing import TextIO

import typer

_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_SECTION_HEADINGS = {
    "ENTRY",
    "RISK",
    "TARGETS",
    "SETUP",
    "WHY THIS TRADE",
    "WARNINGS",
}
_SCORE_LABELS = {
    "Confidence",
    "Setup quality",
    "Execution quality",
    "Target quality",
    "Risk quality",
    "Overall quality",
}
_WARNING_CRITICAL_TERMS = (
    "invalidated",
    "no post-confirmation execution room",
    "critical",
    "prohibited",
    "fully opposed",
    "below minimum",
)
_WARNING_MEDIUM_TERMS = (
    "provisional",
    "wait for",
    "monitor",
    "incomplete",
    "mismatch",
    "opposes",
    "caution",
)
_FIELD_PATTERN = re.compile(r"^(?P<indent>\s*)(?P<label>[^:]+?)(?P<gap>\s{2,})(?P<value>\S.*)$")
_SCORE_PATTERN = re.compile(r"(?P<score>\d+(?:\.\d+)?)/100")
_R_PATTERN = re.compile(r"(?P<value>-?\d+(?:\.\d+)?)R\s+(?P<kind>net|gross)", re.IGNORECASE)


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


def _score_color(score: float) -> str:
    if score >= 70.0:
        return typer.colors.BRIGHT_GREEN
    if score >= 45.0:
        return typer.colors.YELLOW
    return typer.colors.BRIGHT_RED


def _risk_reward_color(value: float) -> str:
    if value >= 1.5:
        return typer.colors.BRIGHT_GREEN
    if value >= 1.0:
        return typer.colors.YELLOW
    return typer.colors.BRIGHT_RED


def _warning_color(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in _WARNING_CRITICAL_TERMS):
        return typer.colors.BRIGHT_RED
    if any(term in lowered for term in _WARNING_MEDIUM_TERMS):
        return typer.colors.YELLOW
    return typer.colors.BRIGHT_WHITE


def _emit_field_line(line: str) -> bool:
    match = _FIELD_PATTERN.match(line)
    if match is None:
        return False

    indent = match.group("indent")
    label = match.group("label").strip()
    gap = match.group("gap")
    value = match.group("value")
    color: str | None = None
    bold = False

    if label == "CMP":
        color = typer.colors.BRIGHT_YELLOW
        bold = True
    elif label in _SCORE_LABELS:
        score_match = _SCORE_PATTERN.search(value)
        if score_match is not None:
            color = _score_color(float(score_match.group("score")))
            bold = True
    elif label == "Gross / net R":
        r_match = _R_PATTERN.search(value)
        if r_match is not None:
            color = _risk_reward_color(float(r_match.group("value")))
            bold = True
    elif value == "Unavailable":
        color = typer.colors.BRIGHT_BLACK
    elif label in {"Execution", "Next action"} and value.lower() in {
        "monitor only",
        "do not enter now",
    }:
        color = typer.colors.YELLOW
        bold = True

    if color is None:
        return False

    typer.echo(f"{indent}{label}{gap}", nl=False)
    typer.secho(value, fg=color, bold=bold)
    return True


def emit_terminal(text: str) -> None:
    """Print reports with a restrained semantic color hierarchy."""

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
        elif stripped in _SECTION_HEADINGS:
            typer.secho(line, fg=typer.colors.BRIGHT_CYAN, bold=True)
        elif stripped.startswith(("Post-entry stop ", "Stop loss ")):
            typer.secho(line, fg=typer.colors.BRIGHT_RED)
        elif stripped.startswith(("Invalidation ", "Pre-entry invalidation ")):
            color = typer.colors.BRIGHT_BLACK if "Unavailable" in line else typer.colors.BRIGHT_RED
            typer.secho(line, fg=color)
        elif stripped.startswith(("TP1 ", "TP2 ", "TP3 ")):
            typer.secho(line, fg=typer.colors.BRIGHT_GREEN)
        elif stripped.startswith("- "):
            typer.secho(line, fg=_warning_color(stripped), bold=True)
        elif upper.startswith(("CRITICAL ", "ERROR ", "INVALIDATED ")):
            typer.secho(line, fg=typer.colors.BRIGHT_RED, bold=True)
        elif upper.startswith(("WARNING ", "MEDIUM ", "CAUTION ")) or line.startswith("!"):
            typer.secho(line, fg=typer.colors.YELLOW, bold=True)
        elif _emit_field_line(line):
            continue
        else:
            typer.echo(line)


__all__ = ["CliProgress", "cli_progress", "emit_terminal"]
