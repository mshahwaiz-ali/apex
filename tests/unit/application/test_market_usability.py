from __future__ import annotations

from apex.application.market_usability import (
    MarketUsabilityState,
    classify_market_usability,
    market_usability_payload,
)


def _quality(
    *,
    stale: bool = False,
    confidence: float = 1.0,
    spread: float | None = 0.05,
    filters: bool = True,
) -> dict[str, object]:
    return {
        "is_stale": stale,
        "data_confidence": confidence,
        "spread_percentage": spread,
        "order_book_spread_percentage": None,
        "exchange_tick_size": 0.01 if filters else None,
        "exchange_step_size": 0.001 if filters else None,
    }


def test_market_usability_is_usable_for_current_complete_data() -> None:
    assessment = classify_market_usability({"15m": _quality()})

    assert assessment.state is MarketUsabilityState.USABLE
    assert assessment.warnings == ()
    assert assessment.missing_inputs == ()


def test_market_usability_uses_caution_for_elevated_spread() -> None:
    assessment = classify_market_usability({"15m": _quality(spread=0.2)})

    assert assessment.state is MarketUsabilityState.USABLE_WITH_CAUTION
    assert any("spread is elevated" in item for item in assessment.warnings)


def test_market_usability_rejects_stale_or_excessive_spread_data() -> None:
    stale = classify_market_usability({"15m": _quality(stale=True)})
    wide = classify_market_usability({"15m": _quality(spread=0.5)})

    assert stale.state is MarketUsabilityState.UNUSABLE
    assert wide.state is MarketUsabilityState.UNUSABLE


def test_market_usability_marks_missing_data_incomplete() -> None:
    assessment = classify_market_usability({})
    payload = market_usability_payload(assessment)

    assert assessment.state is MarketUsabilityState.DATA_INCOMPLETE
    assert payload["state"] == "data_incomplete"
    assert payload["missing_inputs"] == ["timeframe_data_quality"]


def test_missing_execution_metadata_is_caution_not_hard_rejection() -> None:
    assessment = classify_market_usability({"15m": _quality(spread=None, filters=False)})

    assert assessment.state is MarketUsabilityState.USABLE_WITH_CAUTION
    assert "15m:spread" in assessment.missing_inputs
    assert "15m:tick_size" in assessment.missing_inputs
    assert "15m:step_size" in assessment.missing_inputs
