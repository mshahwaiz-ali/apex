"""Tests for deterministic funded futures-plan generation CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from apex.cli_commands import funded_plan_generation

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    funded_plan_generation.register_funded_plan_generation_commands(app)
    return app


def _inputs(tmp_path: Path) -> list[str]:
    args: list[str] = []
    for option, name in (
        ("--setup", "setup.json"),
        ("--account", "account.json"),
        ("--policy", "policy.json"),
        ("--state", "state.json"),
        ("--provider-binding", "binding.json"),
    ):
        path = tmp_path / name
        path.write_text("{}\n", encoding="utf-8")
        args.extend((option, str(path)))
    return args


def _stub_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(funded_plan_generation, "_load_model", lambda *args: object())


def test_generation_writes_non_authorizing_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_models(monkeypatch)
    monkeypatch.setattr(
        funded_plan_generation,
        "build_funded_futures_plan_result",
        lambda *args, **kwargs: {
            "status": "APPROVED",
            "funded_eligibility": {
                "state": "ELIGIBLE_FOR_FUNDED_REVIEW",
                "reasons": [],
                "execution_authorized": False,
            },
            "execution_authorized": False,
        },
    )
    output = tmp_path / "reports" / "plan.json"

    result = runner.invoke(
        _app(),
        [*_inputs(tmp_path), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert "FUNDED_PLAN_GENERATED" in result.output
    assert "funded_state=ELIGIBLE_FOR_FUNDED_REVIEW" in result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["execution_authorized"] is False


def test_generation_rejects_authorizing_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_models(monkeypatch)
    monkeypatch.setattr(
        funded_plan_generation,
        "build_funded_futures_plan_result",
        lambda *args, **kwargs: {"execution_authorized": True},
    )
    output = tmp_path / "plan.json"

    result = runner.invoke(
        _app(),
        [*_inputs(tmp_path), "--output", str(output)],
    )

    assert result.exit_code != 0
    assert "must remain non-authorizing" in result.output
    assert not output.exists()


def test_generation_requires_force_to_replace_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_models(monkeypatch)
    output = tmp_path / "plan.json"
    output.write_text("existing\n", encoding="utf-8")

    result = runner.invoke(
        _app(),
        [*_inputs(tmp_path), "--output", str(output)],
    )

    assert result.exit_code != 0
    assert "output already exists" in result.output
    assert output.read_text(encoding="utf-8") == "existing\n"
