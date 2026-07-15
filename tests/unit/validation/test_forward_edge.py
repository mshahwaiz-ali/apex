"""Tests for N4.10 forward-paper evidence attachment."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from apex.backtesting import BacktestSignal
from apex.paper_trading import PaperTrade, PaperTradeState
from apex.strategies import StrategyType, TradeDirection
from apex.validation.forward_edge import (
    ForwardEdgePolicy,
    build_forward_edge_report,
    load_forward_edge_report,
    write_forward_edge_report,
)


def _validation_report(tmp_path: Path, *, promoted: bool = True) -> Path:
    path = tmp_path / "historical-validation.json"
    payload = {
        "schema_version": 1,
        "report_id": "historical-validation-example",
        "campaign_id": "campaign",
        "results": [
            {
                "dimensions": {
                    "market_type": "futures",
                    "strategy": "trend_pullback",
                    "direction": "long",
                    "symbol": "BTC/USDT",
                    "market_regime": "trend",
                    "score_band": "70_79",
                    "entry_state": "READY_NOW",
                    "risk_mode": "STANDARD",
                },
                "final_test_expectancy": 0.5,
                "promoted_evidence_quality": (
                    "VALIDATED_OUT_OF_SAMPLE" if promoted else None
                ),
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _trade(index: int, realized_r: float) -> PaperTrade:
    time = datetime(2026, 7, 15, 0, index, tzinfo=UTC)
    signal = BacktestSignal(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=time,
        entry_price=100.0,
        stop_price=98.0,
        target_price=102.0,
        quantity=1.0,
        risk_amount=2.0,
        confidence_score=78.0,
    )
    return PaperTrade(
        trade_id=f"paper-{index}",
        signal=signal,
        state=PaperTradeState.TARGET_HIT if realized_r > 0 else PaperTradeState.STOPPED,
        created_at=time,
        updated_at=time,
        analysis_payload={
            "market_regime": "trend",
            "entry_state": "READY_NOW",
            "risk_mode": "STANDARD",
        },
        exit_time=time,
        exit_price=102.0 if realized_r > 0 else 98.0,
        net_pnl=realized_r * 2.0,
        realized_r_multiple=realized_r,
    )


def test_promotes_matching_forward_paper_segment_and_round_trips(tmp_path: Path) -> None:
    historical = _validation_report(tmp_path)
    trades = tuple(_trade(index, 1.0 if index % 3 else -1.0) for index in range(1, 31))

    report = build_forward_edge_report(
        historical_validation_path=historical,
        paper_trades=trades,
        generated_at=datetime(2026, 7, 15, tzinfo=UTC),
        policy=ForwardEdgePolicy(minimum_closed_trades=30),
    )

    assert report["validated_forward_paper_count"] == 1
    result = report["results"][0]
    assert result["status"] == "PASSED_FORWARD_PAPER"
    assert result["promoted_evidence_quality"] == "VALIDATED_FORWARD_PAPER"

    output = tmp_path / "forward.json"
    write_forward_edge_report(output, report)
    assert load_forward_edge_report(output) == report


def test_requires_historical_validation_and_minimum_sample(tmp_path: Path) -> None:
    historical = _validation_report(tmp_path, promoted=False)
    report = build_forward_edge_report(
        historical_validation_path=historical,
        paper_trades=(_trade(1, 1.0),),
        generated_at=datetime(2026, 7, 15, tzinfo=UTC),
    )

    result = report["results"][0]
    assert result["status"] == "FAILED_FORWARD_PAPER"
    assert "HISTORICAL_OUT_OF_SAMPLE_REQUIRED" in result["rejection_reasons"]
    assert "FORWARD_SAMPLE_INSUFFICIENT" in result["rejection_reasons"]
