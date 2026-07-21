from __future__ import annotations

from apex.backtesting.methodology_segmentation import methodology_segment_metrics


def test_segments_required_methodology_dimensions() -> None:
    records = [
        {
            "strategy": "momentum_breakout",
            "lane": "cmp_scalp",
            "direction": "long",
            "continuation_state": "fresh_continuation",
            "layered_state": {
                "timeframe_relationship": "with_trend",
                "continuation_state": "fresh_continuation",
                "execution_state": "clean",
            },
            "replay_reason_code": "canonical_executable_opportunity",
            "future_replay": {"outcome": "target", "realized_r_multiple": 2.0},
        },
        {
            "strategy": "momentum_breakout",
            "lane": "cmp_scalp",
            "direction": "long",
            "continuation_state": "fresh_continuation",
            "layered_state": {
                "timeframe_relationship": "with_trend",
                "continuation_state": "fresh_continuation",
                "execution_state": "clean",
            },
            "replay_reason_code": "canonical_executable_opportunity",
            "future_replay": {"outcome": "stop", "realized_r_multiple": -1.0},
        },
    ]

    payload = methodology_segment_metrics(records)

    assert set(payload) == {
        "strategy",
        "lane",
        "direction",
        "timeframe_relationship",
        "continuation_state",
        "execution_state",
    }
    assert payload["strategy"][0]["sample_size"] == 2
    assert payload["strategy"][0]["win_rate"] == 0.5
    assert payload["strategy"][0]["expectancy_r"] == 0.5
    assert payload["strategy"][0]["calibration_authoritative"] is False


def test_missing_dimensions_and_no_signal_fail_closed() -> None:
    payload = methodology_segment_metrics(
        [
            {
                "replay_reason_code": "canonical_opportunity_invalidated",
                "future_replay": {
                    "outcome": "no_signal",
                    "realized_r_multiple": None,
                },
            }
        ]
    )

    lane = payload["lane"][0]
    assert lane["segment"] == "unavailable"
    assert lane["resolved_outcome_count"] == 0
    assert lane["no_signal_count"] == 1
    assert lane["invalidation_count"] == 1
    assert lane["win_rate"] is None
    assert lane["expectancy_r"] is None
    assert lane["calibration_authoritative"] is False
