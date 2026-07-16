"""Regression tests for single-symbol closed-candle request geometry."""

import pytest

from apex.application import decision_analysis


def test_single_analysis_requests_one_extra_raw_candle(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, int] = {}

    def fake_analyze_symbol(*args: object, **kwargs: object) -> None:
        captured["candle_limit"] = int(kwargs["candle_limit"])
        raise RuntimeError("stop after request capture")

    monkeypatch.setattr(decision_analysis._integrated, "analyze_symbol", fake_analyze_symbol)

    with pytest.raises(RuntimeError, match="stop after request capture"):
        decision_analysis.analyze_symbol(
            "TRX/USDT",
            object(),  # type: ignore[arg-type]
            timeframes=("1m",),
            candle_limit=200,
        )

    assert captured["candle_limit"] == 201
