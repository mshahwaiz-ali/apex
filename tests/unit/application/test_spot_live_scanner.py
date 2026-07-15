from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from apex.application import spot_live_scanner
from apex.domain.spot_market import (
    SpotEligibilityReason,
    SpotEligibilityResult,
    SpotMarketMetadata,
    SpotScannerMode,
)


def _analysis(*, plan: bool = False, approved: bool = False, evidence: int = 1) -> Any:
    selected = SimpleNamespace(
        decision=SimpleNamespace(value="APPROVE" if approved else "WATCH"),
        evidence=tuple(str(index) for index in range(evidence)),
    )
    return SimpleNamespace(
        planning=object() if plan else None,
        routing=SimpleNamespace(selected=selected),
    )


def _metadata(symbol: str) -> SpotMarketMetadata:
    return SpotMarketMetadata(
        symbol=symbol,
        base_asset=symbol.removesuffix("USDT"),
        quote_asset="USDT",
        quote_volume_24h=50_000_000.0,
        spread_percentage=0.05,
        market_age_days=None,
        available_candle_count=200,
        has_data_gaps=False,
        atr_percentage=1.0,
        downside_volatility_percentage=1.0,
        terminal_extension=False,
    )


def _context() -> dict[str, Any]:
    return {
        "account_input": SimpleNamespace(account=SimpleNamespace(quote_asset="USDT")),
        "candle_provider": SimpleNamespace(fetch_candles=lambda *args, **kwargs: []),
        "ticker_provider": SimpleNamespace(fetch_ticker=lambda symbol: object()),
        "product_config": SimpleNamespace(
            eligibility=SimpleNamespace(minimum_candle_count=60),
            structure=SimpleNamespace(terminal_extension_atr_multiple=4.0),
        ),
        "strategy_config": object(),
    }


def _install_eligibility(monkeypatch, reasons_by_symbol: dict[str, tuple[SpotEligibilityReason, ...]]) -> None:
    monkeypatch.setattr(
        spot_live_scanner,
        "build_spot_market_metadata",
        lambda **kwargs: _metadata(kwargs["symbol"]),
    )

    def evaluate(metadata, thresholds):
        reasons = reasons_by_symbol[metadata.symbol]
        return SpotEligibilityResult(
            eligible=reasons == (SpotEligibilityReason.ELIGIBLE,),
            reasons=reasons,
        )

    monkeypatch.setattr(spot_live_scanner, "evaluate_spot_symbol_eligibility", evaluate)


def test_live_scan_deduplicates_and_ranks_eligible_plan_first(monkeypatch) -> None:
    _install_eligibility(
        monkeypatch,
        {
            "BTCUSDT": (SpotEligibilityReason.ELIGIBLE,),
            "ETHUSDT": (SpotEligibilityReason.ELIGIBLE,),
        },
    )
    results = {
        "BTCUSDT": _analysis(plan=False, approved=True, evidence=4),
        "ETHUSDT": _analysis(plan=True, approved=True, evidence=2),
    }
    monkeypatch.setattr(
        spot_live_scanner,
        "analyze_live_spot",
        lambda **kwargs: results[kwargs["symbol"]],
    )

    result = spot_live_scanner.scan_live_spot(
        symbols=(" btcusdt ", "ETHUSDT", "BTCUSDT"),
        mode=SpotScannerMode.ELIGIBLE,
        **_context(),
    )

    assert [item.symbol for item in result.ranked] == ["ETHUSDT", "BTCUSDT"]
    assert result.ineligible == ()
    assert result.failures == ()


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (SpotScannerMode.ELIGIBLE, ["BTCUSDT"]),
        (SpotScannerMode.WATCHLIST, ["BTCUSDT", "ETHUSDT"]),
        (SpotScannerMode.ALL, ["BTCUSDT", "ETHUSDT", "BADUSDT"]),
    ],
)
def test_live_scan_mode_behavior(monkeypatch, mode: SpotScannerMode, expected: list[str]) -> None:
    _install_eligibility(
        monkeypatch,
        {
            "BTCUSDT": (SpotEligibilityReason.ELIGIBLE,),
            "ETHUSDT": (SpotEligibilityReason.TERMINAL_EXTENSION,),
            "BADUSDT": (SpotEligibilityReason.SPREAD_TOO_WIDE,),
        },
    )
    monkeypatch.setattr(
        spot_live_scanner,
        "analyze_live_spot",
        lambda **kwargs: _analysis(),
    )

    result = spot_live_scanner.scan_live_spot(
        symbols=("BTCUSDT", "ETHUSDT", "BADUSDT"),
        mode=mode,
        **_context(),
    )

    assert [item.symbol for item in result.ranked] == expected
    assert [item.symbol for item in result.ineligible] == ["BADUSDT", "ETHUSDT"]


def test_live_scan_isolates_provider_failure_before_eligibility(monkeypatch) -> None:
    context = _context()

    def fetch_ticker(symbol: str) -> object:
        if symbol == "BADUSDT":
            raise ValueError("fixture provider failure")
        return object()

    context["ticker_provider"] = SimpleNamespace(fetch_ticker=fetch_ticker)
    _install_eligibility(monkeypatch, {"GOODUSDT": (SpotEligibilityReason.ELIGIBLE,)})
    monkeypatch.setattr(
        spot_live_scanner,
        "analyze_live_spot",
        lambda **kwargs: _analysis(),
    )

    result = spot_live_scanner.scan_live_spot(
        symbols=("GOODUSDT", "BADUSDT"),
        **context,
    )

    assert [item.symbol for item in result.ranked] == ["GOODUSDT"]
    assert [(item.symbol, item.error) for item in result.failures] == [
        ("BADUSDT", "fixture provider failure")
    ]


def test_live_scan_rejects_empty_universe() -> None:
    with pytest.raises(ValueError, match="at least one symbol"):
        spot_live_scanner.scan_live_spot(symbols=("", "  "), **_context())
