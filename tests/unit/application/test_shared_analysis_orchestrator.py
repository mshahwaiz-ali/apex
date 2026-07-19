from __future__ import annotations

from types import SimpleNamespace

from apex.application import decision_analysis, selected_symbol
from apex.application.opportunity_portfolio import AnalysisMode


def _analysis(symbol: str, mode: AnalysisMode) -> SimpleNamespace:
    return SimpleNamespace(
        symbol=symbol,
        assessment=SimpleNamespace(setup=None, developing_setup=None),
        candidate_ranking=None,
        opportunity_portfolio=SimpleNamespace(
            analysis_mode=mode,
            all_opportunities=(),
        ),
    )


def test_scan_and_analyze_use_the_same_symbol_analysis_boundary(monkeypatch) -> None:
    calls: list[tuple[str, tuple[str, ...], AnalysisMode]] = []

    def shared_analyzer(
        symbol: str,
        provider: object,
        **kwargs: object,
    ) -> SimpleNamespace:
        del provider
        mode = kwargs["analysis_mode"]
        timeframes = tuple(kwargs["timeframes"])
        assert isinstance(mode, AnalysisMode)
        calls.append((symbol, timeframes, mode))
        return _analysis(symbol, mode)

    monkeypatch.setattr(decision_analysis, "analyze_symbol", shared_analyzer)
    monkeypatch.setattr(selected_symbol, "analyze_symbol", shared_analyzer)
    monkeypatch.setattr(
        decision_analysis,
        "_scan_sort_key",
        lambda analysis: (0, 0.0, 0, analysis.symbol),
    )

    analyzed = selected_symbol.analyze_selected_symbol(
        "BTCUSDT",
        object(),
        timeframes=("1m", "5m", "15m"),
    )
    scanned = decision_analysis.scan_symbols(
        ("BTC/USDT",),
        object(),
        timeframes=("1m", "5m", "15m"),
    )

    assert analyzed.symbol == scanned.analyses[0].symbol
    assert calls == [
        (
            "BTC/USDT",
            ("1m", "5m", "15m"),
            AnalysisMode.ANALYZE_FULL,
        ),
        (
            "BTC/USDT",
            ("1m", "5m", "15m"),
            AnalysisMode.SCAN_CMP_FIRST,
        ),
    ]


def test_mode_changes_identity_not_shared_validity_inputs(monkeypatch) -> None:
    captured: list[dict[str, object]] = []

    def shared_analyzer(
        symbol: str,
        provider: object,
        **kwargs: object,
    ) -> SimpleNamespace:
        del provider
        captured.append({"symbol": symbol, **kwargs})
        return _analysis(symbol, kwargs["analysis_mode"])

    monkeypatch.setattr(decision_analysis, "analyze_symbol", shared_analyzer)
    monkeypatch.setattr(selected_symbol, "analyze_symbol", shared_analyzer)
    monkeypatch.setattr(
        decision_analysis,
        "_scan_sort_key",
        lambda analysis: (0, 0.0, 0, analysis.symbol),
    )

    common = {
        "timeframes": ("1m", "5m"),
        "candle_limit": 144,
        "methodology_gate_mode": "shadow",
        "futures_evidence_enabled": False,
    }
    selected_symbol.analyze_selected_symbol("ETHUSDT", object(), **common)
    decision_analysis.scan_symbols(("ETH/USDT",), object(), **common)

    analyze_call, scan_call = captured
    assert analyze_call["symbol"] == scan_call["symbol"] == "ETH/USDT"

    analyze_mode = analyze_call.pop("analysis_mode")
    scan_mode = scan_call.pop("analysis_mode")
    assert analyze_mode is AnalysisMode.ANALYZE_FULL
    assert scan_mode is AnalysisMode.SCAN_CMP_FIRST

    analyze_generated_at = analyze_call.pop("generated_at")
    scan_generated_at = scan_call.pop("generated_at")
    assert analyze_generated_at is None
    assert scan_generated_at is not None
    assert analyze_call == scan_call
