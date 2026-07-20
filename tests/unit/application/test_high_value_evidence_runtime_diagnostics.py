from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.application.discovery_analysis import analyze_symbol
from apex.domain.models import Candle

DECISION_TIME = datetime(2026, 7, 20, 12, 30, tzinfo=UTC)


class _Provider:
    name = "fixture"

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        minutes = {"5m": 5, "15m": 15, "1h": 60}[timeframe]
        count = max(60, limit)
        start = DECISION_TIME - timedelta(minutes=minutes * count)
        candles: list[Candle] = []
        for index in range(count):
            opened = start + timedelta(minutes=minutes * index)
            base = 100.0 + index * 0.08
            close = base + (0.04 if index % 2 == 0 else -0.02)
            candles.append(
                Candle(
                    symbol=symbol,
                    timeframe=timeframe,
                    open_time=opened,
                    close_time=opened + timedelta(minutes=minutes),
                    open=base,
                    high=max(base, close) + 0.2,
                    low=min(base, close) - 0.2,
                    close=close,
                    volume=100.0 + index,
                    is_closed=True,
                    source=self.name,
                )
            )
        return candles[-limit:]


def test_shared_analysis_exposes_runtime_high_value_evidence_diagnostics(
    monkeypatch: object,
) -> None:
    monkeypatch.setattr(
        "apex.application.discovery_analysis._build_native_methodology_snapshot",
        lambda *args, **kwargs: None,
    )
    result = analyze_symbol(
        "BTCUSDT",
        _Provider(),
        timeframes=("5m", "15m", "1h"),
        generated_at=DECISION_TIME,
        futures_evidence_enabled=False,
    )

    diagnostics = result.phase5_diagnostics["high_value_evidence_runtime"]

    assert diagnostics["available_features"] == []
    assert diagnostics["taker_flow_imbalance_proxy"] is None
    assert diagnostics["price_open_interest_relationship"] is None
    assert diagnostics["unavailable_reasons"] == [
        {
            "feature": "price_open_interest_relationship",
            "reason": "market_evidence_unavailable",
        },
        {
            "feature": "taker_flow_imbalance_proxy",
            "reason": "market_evidence_unavailable",
        },
    ]
