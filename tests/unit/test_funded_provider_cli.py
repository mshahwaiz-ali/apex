from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.testing import CliRunner

from apex.cli_commands.funded_provider import register_funded_provider_commands

runner = CliRunner()


def _app() -> typer.Typer:
    app = typer.Typer(no_args_is_help=True)
    register_funded_provider_commands(app)
    return app


def _write_registry(path: Path) -> None:
    path.write_text(
        "schema_version: 1\n"
        "maximum_verification_age_days: 30\n"
        "presets:\n"
        "  - provider_id: EXAMPLE\n"
        "    provider_name: Example Funded\n"
        "    challenge_phase: PHASE_1\n"
        "    verified_on: '2026-07-01'\n"
        "    source_reference: https://example.invalid/rules\n"
        "    drawdown_model: STATIC\n"
        "    external_daily_drawdown_limit_pct: 5.0\n"
        "    external_total_drawdown_limit_pct: 10.0\n"
        "    maximum_trades_per_day: 3\n"
        "    weekend_trading_allowed: false\n"
        "    overnight_holding_allowed: true\n"
        "    news_trading_allowed: false\n"
        "    limits_verified: true\n",
        encoding="utf-8",
    )


def _write_policies(path: Path, *, provider_name: str = "Example Funded") -> None:
    path.write_text(
        "default_policy: FUNDED_EXAMPLE\n"
        "policies:\n"
        "  FUNDED_EXAMPLE:\n"
        "    type: FUNDED\n"
        f"    provider_name: {provider_name}\n"
        "    challenge_phase: PHASE_1\n"
        "    initial_balance: 50000.0\n"
        "    external_daily_drawdown_limit_pct: 5.0\n"
        "    external_total_drawdown_limit_pct: 10.0\n"
        "    internal_daily_stop_pct: 1.0\n"
        "    internal_total_drawdown_buffer_pct: 2.0\n"
        "    maximum_risk_per_trade_pct: 0.25\n"
        "    maximum_total_open_risk_pct: 0.75\n"
        "    maximum_directional_exposure_pct: 20.0\n"
        "    maximum_correlated_exposure_pct: 15.0\n"
        "    maximum_trades_per_day: 3\n"
        "    maximum_consecutive_losses: 2\n"
        "    required_stop_loss: true\n"
        "    weekend_trading_allowed: false\n"
        "    overnight_holding_allowed: true\n"
        "    news_trading_allowed: false\n"
        "    allowed_sessions: []\n",
        encoding="utf-8",
    )


def _write_template(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "risk_mode": "STANDARD",
                "daily_lockout_verified": True,
                "total_buffer_verified": True,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_commands_are_registered() -> None:
    result = runner.invoke(_app(), ["--help"])
    assert result.exit_code == 0
    assert "funded-provider-registry-normalize" in result.output
    assert "funded-provider-prepare" in result.output


def test_registry_normalize_and_prepare_readiness_input(tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"
    normalized = tmp_path / "registry.json"
    policies = tmp_path / "account-policies.yaml"
    template = tmp_path / "template.json"
    output = tmp_path / "readiness-input.json"
    _write_registry(registry)
    _write_policies(policies)
    _write_template(template)

    normalized_result = runner.invoke(
        _app(),
        [
            "funded-provider-registry-normalize",
            "--registry",
            str(registry),
            "--output",
            str(normalized),
        ],
    )
    assert normalized_result.exit_code == 0, normalized_result.output
    assert "FUNDED_PROVIDER_REGISTRY_NORMALIZED" in normalized_result.output

    prepared = runner.invoke(
        _app(),
        [
            "funded-provider-prepare",
            "--registry",
            str(normalized),
            "--provider-id",
            "EXAMPLE",
            "--challenge-phase",
            "PHASE_1",
            "--as-of",
            "2026-07-16",
            "--account-policies",
            str(policies),
            "--policy",
            "FUNDED_EXAMPLE",
            "--template",
            str(template),
            "--output",
            str(output),
        ],
    )
    assert prepared.exit_code == 0, prepared.output
    assert "FUNDED_PROVIDER_READINESS_INPUT_PREPARED" in prepared.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["provider_limits"]["provider_name"] == "Example Funded"
    assert payload["provider_verification"]["provider_id"] == "EXAMPLE"
    assert payload["provider_policy_binding"]["compatible"] is True
    assert payload["provider_policy_binding"]["news_trading_allowed"] is False
    assert payload["provider_policy_binding"]["execution_authorized"] is False
    assert payload["execution_authorized"] is False


def test_prepare_rejects_stale_limits_and_policy_mismatch(tmp_path: Path) -> None:
    registry = tmp_path / "registry.yaml"
    policies = tmp_path / "account-policies.yaml"
    template = tmp_path / "template.json"
    _write_registry(registry)
    _write_policies(policies, provider_name="Other Provider")
    _write_template(template)

    stale = runner.invoke(
        _app(),
        [
            "funded-provider-prepare",
            "--registry",
            str(registry),
            "--provider-id",
            "EXAMPLE",
            "--challenge-phase",
            "PHASE_1",
            "--as-of",
            "2026-09-01",
            "--account-policies",
            str(policies),
            "--policy",
            "FUNDED_EXAMPLE",
            "--template",
            str(template),
            "--output",
            str(tmp_path / "stale.json"),
        ],
    )
    assert stale.exit_code != 0
    assert "stale or future-dated" in stale.output

    mismatch = runner.invoke(
        _app(),
        [
            "funded-provider-prepare",
            "--registry",
            str(registry),
            "--provider-id",
            "EXAMPLE",
            "--challenge-phase",
            "PHASE_1",
            "--as-of",
            "2026-07-16",
            "--account-policies",
            str(policies),
            "--policy",
            "FUNDED_EXAMPLE",
            "--template",
            str(template),
            "--output",
            str(tmp_path / "mismatch.json"),
        ],
    )
    assert mismatch.exit_code != 0
    assert "provider does not match" in mismatch.output
