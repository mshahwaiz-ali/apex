"""Focused tests for the schema-v2 historical signal campaign CLI."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from apex.backtesting.historical_signal_replay import HistoricalSignalSplit
from apex.cli_app import app
from apex.cli_commands.historical_signal_generation import (
    _echo_completion,
    _load_assumptions,
)
from apex.historical_signals import (
    HistoricalSignalCampaignManifest,
    derive_historical_signal_campaign_id,
)

runner = CliRunner()
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_HASH_A = "a" * 64
_HASH_B = "b" * 64


def _plain_output(result: object) -> str:
    output = str(getattr(result, "output", ""))
    return _ANSI_ESCAPE.sub("", output)


def _compact_output(result: object) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "", _plain_output(result))


def _manifest() -> HistoricalSignalCampaignManifest:
    signal_campaign_id = derive_historical_signal_campaign_id(
        campaign_id="pilot",
        dataset_campaign_plan_id="aligned-plan-a",
        dataset_campaign_execution_id="aligned-execution-b",
        assumptions_hash=_HASH_A,
        records_content_hash=_HASH_B,
    )
    return HistoricalSignalCampaignManifest(
        signal_campaign_id=signal_campaign_id,
        campaign_id="pilot",
        dataset_campaign_plan_id="aligned-plan-a",
        dataset_campaign_execution_id="aligned-execution-b",
        assumptions_hash=_HASH_A,
        records_path="signals.jsonl",
        records_content_hash=_HASH_B,
        record_count=6,
        symbol_order=("BTC/USDT",),
        split_order=(
            HistoricalSignalSplit.TRAIN,
            HistoricalSignalSplit.VALIDATION,
            HistoricalSignalSplit.FINAL_TEST,
        ),
        counts_by_symbol=(("BTC/USDT", 6),),
        counts_by_split=(
            (HistoricalSignalSplit.TRAIN, 2),
            (HistoricalSignalSplit.VALIDATION, 2),
            (HistoricalSignalSplit.FINAL_TEST, 2),
        ),
    )


def test_historical_signal_command_is_registered() -> None:
    result = runner.invoke(
        app,
        ["dataset", "historical-signals-generate", "--help"],
    )

    assert result.exit_code == 0
    output = _compact_output(result)
    assert "historical-signals-generate" in output
    assert "--plan" in output
    assert "--execution-manifest" in output
    assert "--assumptions" in output
    assert "--records-output" in output
    assert "--manifest-output" in output
    assert "--candle-limit" in output


def test_assumptions_loader_requires_json_object(tmp_path: Path) -> None:
    assumptions_path = tmp_path / "assumptions.json"
    assumptions_path.write_text(json.dumps(["invalid"]), encoding="utf-8")

    with pytest.raises(ValueError, match="must be a JSON object"):
        _load_assumptions(assumptions_path)


def test_assumptions_loader_preserves_nested_values(tmp_path: Path) -> None:
    assumptions_path = tmp_path / "assumptions.json"
    assumptions_path.write_text(
        json.dumps(
            {
                "candle_limit": 200,
                "generated_at": datetime(2026, 7, 15, tzinfo=UTC).isoformat(),
                "routing": {"normal": ["trend_pullback"]},
            }
        ),
        encoding="utf-8",
    )

    loaded = _load_assumptions(assumptions_path)

    assert loaded["candle_limit"] == 200
    assert loaded["routing"] == {"normal": ["trend_pullback"]}


def test_cli_rejects_matching_output_paths(tmp_path: Path) -> None:
    plan = tmp_path / "plan.json"
    execution = tmp_path / "dataset-execution.json"
    assumptions = tmp_path / "assumptions.json"
    output_path = tmp_path / "signals.json"

    plan.write_text("{}\n", encoding="utf-8")
    execution.write_text("{}\n", encoding="utf-8")
    assumptions.write_text("{}\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "dataset",
            "historical-signals-generate",
            "--plan",
            str(plan),
            "--execution-manifest",
            str(execution),
            "--assumptions",
            str(assumptions),
            "--records-output",
            str(output_path),
            "--manifest-output",
            str(output_path),
        ],
    )

    assert result.exit_code != 0
    assert "must differ" in _plain_output(result)


def test_completion_summary_uses_final_test_name(capsys: pytest.CaptureFixture[str]) -> None:
    _echo_completion(
        manifest=_manifest(),
        records_output=Path("signals.jsonl"),
        manifest_output=Path("signals.manifest.json"),
        accepted_count=2,
        rejected_count=4,
    )

    output = capsys.readouterr().out
    assert "HISTORICAL_SIGNAL_CAMPAIGN_COMPLETED" in output
    assert "accepted=2" in output
    assert "rejected=4" in output
    assert "train=2" in output
    assert "validation=2" in output
    assert "final_test=2" in output
    assert "final-test" not in output
