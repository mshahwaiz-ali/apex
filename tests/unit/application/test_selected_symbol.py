from datetime import UTC, datetime

from apex.application.analysis import SymbolAnalysis
from apex.application.selected_symbol import analyze_selected_symbol
from apex.risk import RiskAssessment, RiskDecision, RiskRejectionCode

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def test_selected_symbol_is_normalized_before_analysis(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_analyze_symbol(symbol, provider, **kwargs):
        captured["symbol"] = symbol
        captured["provider"] = provider
        captured.update(kwargs)
        return SymbolAnalysis(
            symbol=symbol,
            generated_at=NOW,
            assessment=RiskAssessment(
                symbol=symbol,
                decision_time=NOW,
                decision=RiskDecision.REJECTED,
                setup=None,
                rejection_codes=(RiskRejectionCode.NO_SELECTED_CANDIDATE,),
                reasons=("fixture",),
                configuration_id="test",
            ),
            candidate_count=0,
            evaluated_timeframes=("5m",),
            regime_by_timeframe={},
            data_quality_by_timeframe={},
        )

    monkeypatch.setattr("apex.application.selected_symbol.analyze_symbol", fake_analyze_symbol)
    provider = object()

    result = analyze_selected_symbol(
        " btcusdt ",
        provider,
        timeframes=("5m",),
        candle_limit=80,
        generated_at=NOW,
    )

    assert result.symbol == "BTC/USDT"
    assert captured["symbol"] == "BTC/USDT"
    assert captured["provider"] is provider
    assert captured["timeframes"] == ("5m",)
    assert captured["candle_limit"] == 80
