from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from tests.unit.scoring.test_quality_shadow_rollout import _selection

from apex.application.discovery_setup import build_discovery_assessment
from apex.application.enriched_public_output import (
    _attach_target_runner_diagnostics,
)


def test_public_output_attaches_target_runner_diagnostics() -> None:
    assessment = build_discovery_assessment(_selection())
    payload: dict[str, object] = {}

    _attach_target_runner_diagnostics(
        SimpleNamespace(assessment=assessment),  # type: ignore[arg-type]
        payload,
    )

    diagnostics = payload["target_runner_diagnostics"]
    assert isinstance(diagnostics, dict)
    assert diagnostics["symbol"] == assessment.symbol
    selected = diagnostics["selected_setup"]
    assert isinstance(selected, dict)
    assert "runner_qualified" in selected
    assert "runner_qualification_reason" in selected
    assert selected["targets"]


def test_public_output_preserves_single_tp1_without_runner() -> None:
    assessment = build_discovery_assessment(_selection())
    assert assessment.setup is not None
    setup = assessment.setup
    one_target_setup = replace(
        setup,
        take_profits=(
            replace(
                setup.take_profits[0],
                label="TP1",
                partial_close_pct=100.0,
                runner_qualified=False,
            ),
        ),
        runner_qualified=False,
        runner_qualification_reason="no qualified extension target",
    )
    one_target_assessment = replace(assessment, setup=one_target_setup)
    payload: dict[str, object] = {}

    _attach_target_runner_diagnostics(
        SimpleNamespace(assessment=one_target_assessment),  # type: ignore[arg-type]
        payload,
    )

    diagnostics = payload["target_runner_diagnostics"]
    assert isinstance(diagnostics, dict)
    selected = diagnostics["selected_setup"]
    assert isinstance(selected, dict)
    assert selected["runner_qualified"] is False
    assert selected["runner_qualification_reason"] == ("no qualified extension target")
    targets = selected["targets"]
    assert isinstance(targets, list)
    assert len(targets) == 1
    assert targets[0]["label"] == "TP1"
    assert targets[0]["partial_close_pct"] == 100.0
    assert targets[0]["runner_qualified"] is False


def test_scan_and_analyze_use_shared_enriched_public_output() -> None:
    root = Path(__file__).resolve().parents[3]
    analysis_source = (root / "src/apex/cli_commands/analysis.py").read_text(encoding="utf-8")
    scanner_source = (root / "src/apex/cli_commands/scanner.py").read_text(encoding="utf-8")

    assert (
        "from apex.application.enriched_public_output import serialize_symbol_analysis"
    ) in analysis_source
    assert "serialize_scan_result" in scanner_source
    assert "serialize_symbol_analysis" in scanner_source


def test_shared_core_attaches_target_runner_diagnostics_once() -> None:
    root = Path(__file__).resolve().parents[3]
    source = (root / "src/apex/application/enriched_public_output.py").read_text(encoding="utf-8")

    assert source.count("_attach_target_runner_diagnostics(analysis, payload)") == 1
    assert 'payload["target_runner_diagnostics"]' in source
    assert "serialize_assessment_target_runner_diagnostics" in source
