"""Professional output overlay for legacy research commands."""

from __future__ import annotations

import inspect
import io
import json
from collections.abc import Callable, Mapping
from contextlib import redirect_stdout
from functools import wraps
from typing import Annotated, Any, cast

import typer

from apex.presentation import OutputMode, normalize_cli_output_mode
from apex.presentation.research import render_backtest, render_campaign, render_comparison


_FORMAT_ANNOTATION = Annotated[
    str,
    typer.Option("--format", help="text or json"),
]


def install_research_output_overlay(app: typer.Typer) -> None:
    """Add professional terminal output to core research commands."""

    renderers: dict[str, Callable[[Mapping[str, object], OutputMode], str]] = {
        "chronological-backtest": lambda payload, mode: render_backtest(payload, mode=mode),
        "chronological-backtest-campaign": lambda payload, mode: render_campaign(payload, mode=mode),
        "compare-backtests": lambda payload, mode: render_comparison(payload, mode=mode),
    }
    for command in app.registered_commands:
        name = command.name
        if name not in renderers or command.callback is None:
            continue
        command.callback = _wrap_callback(command.callback, renderers[name])


def _wrap_callback(
    callback: Callable[..., Any],
    renderer: Callable[[Mapping[str, object], OutputMode], str],
) -> Callable[..., Any]:
    original_signature = inspect.signature(callback)

    @wraps(callback)
    def wrapped(*args: object, **kwargs: object) -> Any:
        raw_mode = kwargs.pop("output_format", "text")
        try:
            mode = normalize_cli_output_mode(cast(str, raw_mode))
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

        stream = io.StringIO()
        with redirect_stdout(stream):
            result = callback(*args, **kwargs)
        captured = stream.getvalue()
        if mode is OutputMode.JSON:
            typer.echo(captured, nl=False)
            return result

        payload = _load_payload(captured)
        typer.echo(renderer(payload, mode))
        return result

    parameters = list(original_signature.parameters.values())
    parameters.append(
        inspect.Parameter(
            "output_format",
            kind=inspect.Parameter.KEYWORD_ONLY,
            default="text",
            annotation=_FORMAT_ANNOTATION,
        )
    )
    wrapped.__signature__ = original_signature.replace(parameters=parameters)  # type: ignore[attr-defined]
    return wrapped


def _load_payload(value: str) -> Mapping[str, object]:
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter("research command did not produce a JSON payload") from exc
    if not isinstance(loaded, dict):
        raise typer.BadParameter("research command payload must be a JSON object")
    return cast(dict[str, object], loaded)


__all__ = ["install_research_output_overlay"]
