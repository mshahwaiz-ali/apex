from __future__ import annotations

from types import SimpleNamespace

from apex.application import decision_analysis, selected_symbol
from apex.application.opportunity_portfolio import AnalysisMode


def test_selected_symbol_requests_full_analysis(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_analyze_symbol(symbol: str, provider: object, **kwargs: object) -> object:
        captured["symbol"] = symbol
        captured["provider"] = provider
        captured.update(kwargs)
        return SimpleNamespace(symbol=symbol)

    monkeypatch.setattr(selected_symbol, "analyze_symbol", fake_analyze_symbol)

    result = selected_symbol.analyze_selected_symbol(
        "btcusdt",
        object(),
        timeframes=("1m", "5m"),
    )

    assert result.symbol == "BTC/USDT"
    assert captured["analysis_mode"] is AnalysisMode.ANALYZE_FULL


def test_scan_requests_cmp_first_mode(monkeypatch) -> None:
    modes: list[AnalysisMode] = []

    def fake_analyze_symbol(symbol: str, provider: object, **kwargs: object) -> object:
        modes.append(kwargs["analysis_mode"])
        return SimpleNamespace(
            symbol=symbol,
            assessment=SimpleNamespace(setup=None, developing_setup=None),
            candidate_ranking=None,
        )

    monkeypatch.setattr(decision_analysis, "analyze_symbol", fake_analyze_symbol)
    monkeypatch.setattr(
        decision_analysis,
        "_scan_sort_key",
        lambda analysis: (0, 0.0, 0, analysis.symbol),
    )

    result = decision_analysis.scan_symbols(
        ("BTCUSDT", "ETHUSDT"),
        object(),
        timeframes=("1m", "5m"),
    )

    assert len(result.analyses) == 2
    assert modes == [
        AnalysisMode.SCAN_CMP_FIRST,
        AnalysisMode.SCAN_CMP_FIRST,
    ]
