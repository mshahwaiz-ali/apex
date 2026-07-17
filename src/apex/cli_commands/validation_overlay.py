"""Professional output overlay for validation and readiness commands."""

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
from apex.presentation.validation import render_evidence_bundle, render_validation

_FORMAT_ANNOTATION = Annotated[
    str,
    typer.Option("--format", help="text or json"),
]

_JSON_MODE_COMMANDS = {
    "paper-validation-review",
    "funded-readiness-review",
    "paper-validation-run",
    "funded-readiness-from-report",
    "paper-validation-history-review",
    "funded-readiness-from-history",
}

_TITLES = {
    "paper-validation-review": "Paper Validation Review",
    "funded-readiness-review": "Funded Readiness Review",
    "paper-validation-generate": "Paper Validation Evidence",
    "paper-validation-run": "Paper Validation Pipeline",
    "funded-readiness-from-report": "Funded Readiness From Report",
    "paper-validation-daily": "Daily Paper Validation",
    "paper-validation-history-review": "Validation History Review",
    "funded-readiness-from-history": "Funded Readiness From History",
}


def install_validation_output_overlay(app: typer.Typer) -> None:
    """Add four presentation modes to validation and readiness commands."""

    targets = set(_TITLES) | {"evidence-bundle-inspect"}
    for command in app.registered_commands:
        name = command.name
        if name not in targets or command.callback is None:
            continue
        command.callback = _wrap_callback(command.callback, name)


def _wrap_callback(callback: Callable[..., Any], command_name: str) -> Callable[..., Any]:
    original_signature = inspect.signature(callback)

    @wraps(callback)
    def wrapped(*args: object, **kwargs: object) -> Any:
        raw_mode = kwargs.pop("output_format", "text")
        try:
            mode = normalize_cli_output_mode(cast(str, raw_mode))
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

        if command_name in _JSON_MODE_COMMANDS:
            kwargs["output"] = "json"

        stream = io.StringIO()
        with redirect_stdout(stream):
            result = callback(*args, **kwargs)
        captured = stream.getvalue()
        if mode is OutputMode.JSON:
            typer.echo(captured, nl=False)
            return result

        payload = _load_payload(captured)
        if command_name == "evidence-bundle-inspect":
            rendered = render_evidence_bundle(payload, mode=mode)
        else:
            rendered = render_validation(payload, title=_TITLES[command_name], mode=mode)
        typer.echo(rendered)
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
        raise typer.BadParameter("validation command did not produce a JSON payload") from exc
    if not isinstance(loaded, dict):
        raise typer.BadParameter("validation command payload must be a JSON object")
    return cast(dict[str, object], loaded)


__all__ = ["install_validation_output_overlay"]
