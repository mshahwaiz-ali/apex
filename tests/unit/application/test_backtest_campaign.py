from datetime import UTC, datetime, timedelta

import pytest

from apex.application.backtest_campaign import (
    BacktestCampaignRequest,
    BacktestCampaignVariant,
    MultiSymbolBacktestCampaignRequest,
    campaign_result_to_payload,
    parse_campaign_variants,
    run_backtest_campaign,
    run_multi_symbol_backtest_campaign,
    split_campaign_candles_by_symbol,
)
from apex.application.chronological_backtest import (
    ChronologicalBacktestRequest,
    ChronologicalBacktestResult,
)
from apex.application.chronological_metadata import build_chronological_metadata
from apex.backtesting import BacktestReport
from apex.domain import Candle

NOW = datetime(2026, 7, 14, tzinfo=UTC)


def _candles(count: int, *, symbol: str = "BTC/USDT") -> tuple[Candle, ...]:
    return tuple(
        Candle(
            symbol=symbol,
            timeframe="5m",
            open_time=NOW + timedelta(minutes=5 * index),
            close_time=NOW + timedelta(minutes=5 * (index + 1)),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            volume=1000.0,
            is_closed=True,
            source="fixture",
        )
        for index in range(count)
    )


def _report(*, net_profit: float, expectancy: float = 0.0) -> BacktestReport:
    return BacktestReport(
        trades=(),
        total_trades=0,
        win_rate=0.0,
        loss_rate=0.0,
        breakeven_rate=0.0,
        gross_profit=max(net_profit, 0.0),
        gross_loss=min(net_profit, 0.0),
        net_profit=net_profit,
        profit_factor=None,
        average_win=0.0,
        average_loss=0.0,
        average_risk_reward=0.0,
        expectancy=expectancy,
        maximum_drawdown=0.0,
        consecutive_wins=0,
        consecutive_losses=0,
        by_symbol={},
        by_strategy={},
    )


def _result(
    request: ChronologicalBacktestRequest,
    *,
    net_profit: float,
) -> ChronologicalBacktestResult:
    metadata = build_chronological_metadata(
        symbol=request.symbol,
        candles_by_timeframe=request.candles_by_timeframe,
        analysis_timeframes=request.analysis_timeframes,
        replay_timeframe=request.replay_timeframe,
        candle_limit=request.candle_limit,
        decision_interval_candles=request.decision_interval_candles,
        candidate_cooldown_candles=request.candidate_cooldown_candles,
        risk_config=request.risk_config,
        backtest_config=request.backtest_config,
    )
    return ChronologicalBacktestResult(
        report=_report(net_profit=net_profit, expectancy=net_profit / 10.0),
        trades=(),
        metadata=metadata,
        decision_count=1,
        approved_count=0,
        skipped_count=1,
        cooldown_skipped_count=0,
        overlap_skipped_count=0,
        failure_count=0,
        failures={},
    )


def test_backtest_campaign_runs_variants_and_ranks_best() -> None:
    variants = (
        BacktestCampaignVariant(identifier="baseline", candle_limit=40),
        BacktestCampaignVariant(identifier="candidate", candle_limit=45),
    )
    seen: list[int] = []

    def fake_runner(request: ChronologicalBacktestRequest) -> ChronologicalBacktestResult:
        seen.append(request.candle_limit)
        return _result(
            request,
            net_profit=10.0 if request.candle_limit == 45 else 2.0,
        )

    result = run_backtest_campaign(
        BacktestCampaignRequest(
            symbol="BTC/USDT",
            candles_by_timeframe={"5m": _candles(70)},
            analysis_timeframes=("5m",),
            variants=variants,
            dataset_source="fixture",
        ),
        generated_at=NOW,
        runner=fake_runner,
    )
    payload = campaign_result_to_payload(result)

    assert seen == [40, 45]
    assert result.best_variant_id == "candidate"
    assert payload["schema_version"] == 1
    assert payload["rankings"][0]["variant_id"] == "candidate"
    assert payload["variants"][1]["variant"]["candle_limit"] == 45


def test_backtest_campaign_rejects_duplicate_variant_ids() -> None:
    with pytest.raises(ValueError, match="unique"):
        BacktestCampaignRequest(
            symbol="BTC/USDT",
            candles_by_timeframe={"5m": _candles(70)},
            analysis_timeframes=("5m",),
            variants=(
                BacktestCampaignVariant(identifier="same", candle_limit=40),
                BacktestCampaignVariant(identifier="same", candle_limit=45),
            ),
        )


def test_parse_campaign_variants_accepts_compact_cli_specification() -> None:
    variants = parse_campaign_variants("base:5m:200:1:3,slow:15m:120:3:5")

    assert [variant.identifier for variant in variants] == ["base", "slow"]
    assert variants[1].replay_timeframe == "15m"
    assert variants[1].decision_interval_candles == 3


def test_parse_campaign_variants_rejects_malformed_specification() -> None:
    with pytest.raises(ValueError, match="id:timeframe"):
        parse_campaign_variants("broken:5m")


def test_multi_symbol_campaign_runs_each_symbol_variant_and_ranks_best() -> None:
    variants = (
        BacktestCampaignVariant(identifier="baseline", candle_limit=40),
        BacktestCampaignVariant(identifier="fast", candle_limit=45),
    )
    seen: list[tuple[str, int]] = []

    def fake_runner(request: ChronologicalBacktestRequest) -> ChronologicalBacktestResult:
        seen.append((request.symbol, request.candle_limit))
        return _result(
            request,
            net_profit=20.0 if request.symbol == "ETH/USDT" and request.candle_limit == 45 else 1.0,
        )

    result = run_multi_symbol_backtest_campaign(
        MultiSymbolBacktestCampaignRequest(
            symbols=("BTCUSDT", "ETHUSDT"),
            candles_by_symbol={
                "BTC/USDT": {"5m": _candles(70, symbol="BTC/USDT")},
                "ETH/USDT": {"5m": _candles(70, symbol="ETH/USDT")},
            },
            analysis_timeframes=("5m",),
            variants=variants,
            dataset_source="fixture",
        ),
        generated_at=NOW,
        runner=fake_runner,
    )
    payload = campaign_result_to_payload(result)

    assert seen == [
        ("BTC/USDT", 40),
        ("BTC/USDT", 45),
        ("ETH/USDT", 40),
        ("ETH/USDT", 45),
    ]
    assert result.symbol == "MULTI"
    assert result.best_symbol == "ETH/USDT"
    assert result.best_variant_id == "fast"
    assert payload["symbol_count"] == 2
    assert payload["rankings"][0]["symbol"] == "ETH/USDT"
    assert payload["variants"][0]["symbol"] == "BTC/USDT"


def test_split_campaign_candles_by_symbol_filters_timeframes() -> None:
    split = split_campaign_candles_by_symbol(
        {
            "5m": (
                *_candles(2, symbol="BTC/USDT"),
                *_candles(3, symbol="ETH/USDT"),
            )
        },
        ("BTCUSDT", "ETHUSDT"),
    )

    assert len(split["BTC/USDT"]["5m"]) == 2
    assert len(split["ETH/USDT"]["5m"]) == 3
