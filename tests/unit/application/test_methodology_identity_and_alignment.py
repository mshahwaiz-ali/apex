from __future__ import annotations

from apex.application.analysis_records import build_analysis_record
from apex.application.discovery_analysis import (
    _shared_structure_map_payload,
    _timeframe_alignment_payload,
)
from apex.application.methodology_identity import (
    METHODOLOGY_AUTHORITY_PATH,
    METHODOLOGY_VERSION,
)


def test_analysis_records_include_stable_methodology_identity() -> None:
    record = build_analysis_record(
        {
            "symbol": "BTCUSDT",
            "generated_at": "2026-07-19T00:00:00+00:00",
            "configuration_id": "test-config",
        }
    )

    assert record["methodology_version"] == METHODOLOGY_VERSION
    assert record["methodology_path"] == METHODOLOGY_AUTHORITY_PATH
    assert record["methodology_identity"]["authority_path"] == METHODOLOGY_AUTHORITY_PATH


def test_higher_timeframe_direct_opposition_is_explicit() -> None:
    payload = _timeframe_alignment_payload(
        {
            "1h": {
                "role": "intermediate",
                "structure": {"trend_state": "downtrend"},
            },
            "5m": {
                "role": "entry",
                "structure": {"trend_state": "uptrend"},
            },
            "1m": {
                "role": "timing",
                "structure": {"trend_state": "strong_uptrend"},
            },
        },
        "long",
    )

    assert payload["state"] == "DIRECT_OPPOSITION"
    assert payload["rules"]["timing_override_allowed"] is False
    assert payload["higher_timeframes"] == ["1h"]


def test_missing_higher_timeframe_data_lowers_alignment_confidence() -> None:
    payload = _timeframe_alignment_payload(
        {
            "5m": {
                "role": "entry",
                "structure": {"trend_state": "uptrend"},
            },
            "1m": {
                "role": "timing",
                "structure": {"trend_state": "strong_uptrend"},
            },
        },
        "long",
    )

    assert payload["state"] == "INSUFFICIENT_DATA"
    assert "missing higher-timeframe structure" in payload["reasons"][0]


def test_shared_structure_map_reuses_serialized_frame_structure() -> None:
    source = {
        "15m": {
            "role": "setup",
            "structure": {
                "trend_state": "range",
                "break_state": "NO_BREAK",
                "available_upside_room": 5.0,
            },
        }
    }

    assert _shared_structure_map_payload(source) == {"15m": source["15m"]["structure"]}
