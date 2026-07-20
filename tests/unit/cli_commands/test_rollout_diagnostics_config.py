"""Tests for CLI rollout-diagnostics configuration propagation."""

from __future__ import annotations

from typing import Any, cast

from apex.cli_commands import analysis as analysis_cli
from apex.cli_commands import scanner as scanner_cli


def test_analyze_serialization_defaults_to_disabled(monkeypatch: Any) -> None:
    calls: list[bool] = []

    def fake_serializer(
        result: Any,
        *,
        include_rollout_diagnostics: bool = False,
    ) -> dict[str, Any]:
        del result
        calls.append(include_rollout_diagnostics)
        return {"symbol": "BTCUSDT"}

    monkeypatch.setattr(analysis_cli, "serialize_symbol_analysis", fake_serializer)

    payload = analysis_cli._serialize_analysis_payload(
        cast(Any, object()),
        rollout_diagnostics_enabled=False,
    )

    assert payload == {"symbol": "BTCUSDT"}
    assert calls == [False]


def test_analyze_serialization_enables_diagnostics(monkeypatch: Any) -> None:
    calls: list[bool] = []

    def fake_serializer(
        result: Any,
        *,
        include_rollout_diagnostics: bool = False,
    ) -> dict[str, Any]:
        del result
        calls.append(include_rollout_diagnostics)
        return {"rollout_comparison": {"authoritative": False}}

    monkeypatch.setattr(analysis_cli, "serialize_symbol_analysis", fake_serializer)

    payload = analysis_cli._serialize_analysis_payload(
        cast(Any, object()),
        rollout_diagnostics_enabled=True,
    )

    assert "rollout_comparison" in payload
    assert calls == [True]


def test_scan_serialization_defaults_to_disabled(monkeypatch: Any) -> None:
    calls: list[bool] = []

    def fake_serializer(
        result: Any,
        *,
        display_limit: int,
        direction: str,
        include_rollout_diagnostics: bool = False,
    ) -> dict[str, Any]:
        del result, display_limit, direction
        calls.append(include_rollout_diagnostics)
        return {"results": []}

    monkeypatch.setattr(scanner_cli, "serialize_scan_result", fake_serializer)

    payload = scanner_cli._serialize_scan_payload(
        cast(Any, object()),
        display_limit=20,
        direction="both",
        rollout_diagnostics_enabled=False,
    )

    assert payload == {"results": []}
    assert calls == [False]


def test_scan_serialization_enables_diagnostics(monkeypatch: Any) -> None:
    calls: list[bool] = []

    def fake_serializer(
        result: Any,
        *,
        display_limit: int,
        direction: str,
        include_rollout_diagnostics: bool = False,
    ) -> dict[str, Any]:
        del result, display_limit, direction
        calls.append(include_rollout_diagnostics)
        return {
            "results": [],
            "rollout_comparison_summary": {"authoritative": False},
        }

    monkeypatch.setattr(scanner_cli, "serialize_scan_result", fake_serializer)

    payload = scanner_cli._serialize_scan_payload(
        cast(Any, object()),
        display_limit=20,
        direction="both",
        rollout_diagnostics_enabled=True,
    )

    assert "rollout_comparison_summary" in payload
    assert calls == [True]


def test_scan_record_serialization_uses_same_switch(monkeypatch: Any) -> None:
    calls: list[bool] = []

    def fake_serializer(
        analysis: Any,
        *,
        include_rollout_diagnostics: bool = False,
    ) -> dict[str, Any]:
        del analysis
        calls.append(include_rollout_diagnostics)
        return {"symbol": "ETHUSDT"}

    monkeypatch.setattr(scanner_cli, "serialize_symbol_analysis", fake_serializer)

    disabled = scanner_cli._serialize_scan_analysis_record(
        cast(Any, object()),
        rollout_diagnostics_enabled=False,
    )
    enabled = scanner_cli._serialize_scan_analysis_record(
        cast(Any, object()),
        rollout_diagnostics_enabled=True,
    )

    assert disabled == {"symbol": "ETHUSDT"}
    assert enabled == {"symbol": "ETHUSDT"}
    assert calls == [False, True]
