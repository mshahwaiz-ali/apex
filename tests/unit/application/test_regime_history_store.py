from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from apex.application.regime_history import (
    RegimeHistoryStore,
    RegimeObservation,
    regime_observation_from_analysis,
)


def _observation(at: datetime, selected: str) -> RegimeObservation:
    return RegimeObservation(
        symbol="BTCUSDT",
        observed_at=at,
        raw_state="range",
        selected_state=selected,
        probability=0.6,
    )


def test_regime_history_is_persistent_bounded_and_point_in_time(tmp_path: Path) -> None:
    path = tmp_path / "regime_history.json"
    store = RegimeHistoryStore(path)
    first = datetime(2026, 1, 1, tzinfo=UTC)
    second = first + timedelta(hours=1)

    store.append(_observation(second, "trend"))
    store.append(_observation(first, "range"))

    reloaded = RegimeHistoryStore(path)
    assert reloaded.previous_state("BTCUSDT", before=second) == "range"
    assert (
        reloaded.previous_state(
            "BTCUSDT",
            before=second + timedelta(seconds=1),
        )
        == "trend"
    )
    assert tuple(item.observed_at for item in reloaded.observations("BTCUSDT")) == (
        first,
        second,
    )


def test_regime_observation_requires_complete_analysis_payload() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    observation = regime_observation_from_analysis(
        symbol="ETHUSDT",
        observed_at=now,
        market_intelligence={
            "regime": {
                "raw_state": "trend",
                "state": "range",
                "probability": 0.55,
            }
        },
    )

    assert observation is not None
    assert observation.symbol == "ETHUSDT"
    assert observation.selected_state == "range"
    assert (
        regime_observation_from_analysis(
            symbol="ETHUSDT",
            observed_at=now,
            market_intelligence={"regime": {"state": "range"}},
        )
        is None
    )
