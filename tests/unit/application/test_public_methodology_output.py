from __future__ import annotations

from datetime import UTC, datetime

from apex.application.discovery_contracts import DiscoveryAssessment, SymbolAnalysis
from apex.application.methodology_snapshot import MethodologySnapshot
from apex.application.public_output import serialize_symbol_analysis


def _analysis(*, methodology: MethodologySnapshot | None) -> SymbolAnalysis:
    generated_at = datetime(2026, 7, 18, tzinfo=UTC)
    return SymbolAnalysis(
        symbol="BTCUSDT",
        generated_at=generated_at,
        assessment=DiscoveryAssessment(
            symbol="BTCUSDT",
            decision_time=generated_at,
            setup=None,
            reasons=("no valid setup",),
        ),
        candidate_count=0,
        evaluated_timeframes=("15m",),
        regime_by_timeframe={"15m": "range"},
        data_quality_by_timeframe={},
        methodology=methodology,
    )


def test_public_output_projects_absent_methodology() -> None:
    payload = serialize_symbol_analysis(_analysis(methodology=None))

    assert payload["methodology"] is not None
    assert payload["methodology"]["executable"] is False
    assert payload["methodology"]["hard_blockers"] == []
    assert payload["decision_reason_code"] == "NO_TRADE"


def test_public_output_serializes_stored_methodology_snapshot() -> None:
    payload = serialize_symbol_analysis(_analysis(methodology=MethodologySnapshot()))

    assert payload["methodology"] is not None
    assert payload["methodology"]["executable"] is False
    assert payload["methodology"]["hard_blockers"] == []
