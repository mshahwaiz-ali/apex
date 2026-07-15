from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from apex.application import spot_live_scanner


def _result(*, plan: bool, approved: bool, evidence: int) -> Any:
    selected = SimpleNamespace(
        decision=SimpleNamespace(value="APPROVE" if approved else "WATCH"),
        evidence=tuple(str(index) for index in range(evidence)),
    )
    return SimpleNamespace(
        planning=object() if plan else None,
        routing=SimpleNamespace(selected=selected),
    )


def test_live_scan_deduplicates_and_ranks_plan_first(monkeypatch) -> None:
    results = {
        "BTCUSDT": _result(plan=False, approved=True, evidence=4),
        "ETHUSDT": _result(plan=True, approved=True, evidence=2),
        "SOLUSDT": _result(plan=False, approved=True, evidence=5),
    }

    def analyze(**kwargs):
        return results[kwargs["symbol"]]

    monkeypatch.setattr(spot_live_scanner, "analyze_live_spot", analyze)
    result = spot_live_scanner.scan_live_spot(
        symbols=(" btcusdt ", "ETHUSDT", "BTCUSDT", "SOLUSDT"),
        account_input=object(),
        candle_provider=object(),
        ticker_provider=object(),
        product_config=object(),
        strategy_config=object(),
    )

    assert [item.symbol for item in result.ranked] == ["ETHUSDT", "SOLUSDT", "BTCUSDT"]
    assert result.failures == ()


def test_live_scan_isolates_symbol_failures(monkeypatch) -> None:
    def analyze(**kwargs):
        if kwargs["symbol"] == "BADUSDT":
            raise ValueError("fixture failure")
        return _result(plan=False, approved=False, evidence=1)

    monkeypatch.setattr(spot_live_scanner, "analyze_live_spot", analyze)
    result = spot_live_scanner.scan_live_spot(
        symbols=("GOODUSDT", "BADUSDT"),
        account_input=object(),
        candle_provider=object(),
        ticker_provider=object(),
        product_config=object(),
        strategy_config=object(),
    )

    assert [item.symbol for item in result.ranked] == ["GOODUSDT"]
    assert [(item.symbol, item.error) for item in result.failures] == [
        ("BADUSDT", "fixture failure")
    ]


def test_live_scan_rejects_empty_universe() -> None:
    try:
        spot_live_scanner.scan_live_spot(
            symbols=("", "  "),
            account_input=object(),
            candle_provider=object(),
            ticker_provider=object(),
            product_config=object(),
            strategy_config=object(),
        )
    except ValueError as exc:
        assert "at least one symbol" in str(exc)
    else:
        raise AssertionError("empty universe unexpectedly succeeded")
