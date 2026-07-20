"""Final compatibility and cleanup-readiness audit for Batch 12."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, cast

import pytest

from apex.application import (
    RolloutAcceptanceResult,
    build_rollout_operator_report,
    evaluate_rollout_acceptance,
    rollout_acceptance_payload,
    write_rollout_operator_report,
)
from apex.application import public_output as legacy_public_output
from apex.application.enriched_public_output import (
    serialize_scan_result,
    serialize_symbol_analysis,
)
from apex.application.rollout_comparison import AnalysisComparisonSummary
from apex.cli_commands import analysis as analysis_cli
from apex.cli_commands import scanner as scanner_cli
from apex.config import FileSettings


def _empty_summary() -> AnalysisComparisonSummary:
    return AnalysisComparisonSummary(
        total_count=0,
        match_count=0,
        difference_count=0,
        compatibility_only_count=0,
        regression_count=0,
        field_difference_counts={},
        regression_field_counts={},
        compatibility_fixture_ids=(),
        regression_fixture_ids=(),
    )


def test_rollout_diagnostics_remain_disabled_by_default() -> None:
    settings = FileSettings()

    assert settings.rollout_diagnostics_enabled is False


def test_legacy_public_output_path_is_still_available() -> None:
    assert callable(legacy_public_output.serialize_symbol_analysis)
    assert callable(legacy_public_output.serialize_scan_result)


def test_enriched_serializers_keep_opt_in_default_false() -> None:
    symbol_signature = inspect.signature(serialize_symbol_analysis)
    scan_signature = inspect.signature(serialize_scan_result)

    assert symbol_signature.parameters["include_rollout_diagnostics"].default is False
    assert scan_signature.parameters["include_rollout_diagnostics"].default is False


def test_operator_report_requires_diagnostic_payload() -> None:
    with pytest.raises(ValueError, match="does not contain rollout diagnostics"):
        build_rollout_operator_report({}, command="analyze")

    with pytest.raises(ValueError, match="does not contain rollout diagnostics"):
        build_rollout_operator_report({}, command="scan")


def test_acceptance_is_non_authoritative_and_not_an_exit_gate() -> None:
    result = evaluate_rollout_acceptance(_empty_summary())
    payload = rollout_acceptance_payload(result)

    assert isinstance(result, RolloutAcceptanceResult)
    assert result.authoritative is False
    assert payload["authoritative"] is False
    assert not hasattr(result, "exit_code")


def test_scan_and_analyze_cli_use_explicit_serialization_helpers() -> None:
    analysis_source = inspect.getsource(analysis_cli.register_analysis_commands)
    scanner_source = inspect.getsource(scanner_cli.register_scanner_commands)

    assert "_serialize_analysis_payload(" in analysis_source
    assert "_serialize_scan_payload(" in scanner_source
    assert "_serialize_scan_analysis_record(" in scanner_source


def test_cli_helpers_forward_only_the_diagnostics_switch(monkeypatch: Any) -> None:
    analyze_calls: list[bool] = []
    scan_calls: list[bool] = []

    def fake_analysis_serializer(
        result: Any,
        *,
        include_rollout_diagnostics: bool = False,
    ) -> dict[str, Any]:
        del result
        analyze_calls.append(include_rollout_diagnostics)
        return {}

    def fake_scan_serializer(
        result: Any,
        *,
        display_limit: int,
        direction: str,
        include_rollout_diagnostics: bool = False,
    ) -> dict[str, Any]:
        del result, display_limit, direction
        scan_calls.append(include_rollout_diagnostics)
        return {}

    monkeypatch.setattr(
        analysis_cli,
        "serialize_symbol_analysis",
        fake_analysis_serializer,
    )
    monkeypatch.setattr(scanner_cli, "serialize_scan_result", fake_scan_serializer)

    analysis_cli._serialize_analysis_payload(
        cast(Any, object()),
        rollout_diagnostics_enabled=False,
    )
    scanner_cli._serialize_scan_payload(
        cast(Any, object()),
        display_limit=20,
        direction="both",
        rollout_diagnostics_enabled=False,
    )

    assert analyze_calls == [False]
    assert scan_calls == [False]


def test_rollout_exports_are_available_from_application_facade() -> None:
    assert callable(build_rollout_operator_report)
    assert callable(write_rollout_operator_report)
    assert callable(evaluate_rollout_acceptance)
    assert callable(rollout_acceptance_payload)


def test_rollout_documentation_declares_cleanup_blockers() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    plan = (repo_root / "docs" / "planv3.md").read_text(encoding="utf-8")
    runbook = (repo_root / "docs" / "rollout_operations.md").read_text(encoding="utf-8")

    assert "Final cleanup gate" in plan
    assert "Compatibility-removal prerequisites" in runbook
    assert "rollout_diagnostics_enabled: false" in plan
    assert "regression_count == 0" in runbook
