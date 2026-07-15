"""Contract tests for shared-wallet historical futures integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.backtesting.contracts import BacktestOutcome, BacktestSignal, SimulatedTrade
from apex.backtesting.historical_futures_campaign import (
    HistoricalFuturesCampaignResult,
    HistoricalFuturesExecutionManifest,
    HistoricalFuturesObservation,
    HistoricalFuturesTradeResult,
)
from apex.backtesting.historical_futures_shared_campaign import (
    SharedHistoricalFuturesExecutionManifest,
    _merge_wallet_observations,
    _required_margin_by_key,
)
from apex.backtesting.historical_signal_replay import HistoricalSignalSplit
from apex.strategies import StrategyType, TradeDirection


def _trade_result(result_id: str = "result-1") -> HistoricalFuturesTradeResult:
    generated = datetime(2026, 1, 1, tzinfo=UTC)
    signal = BacktestSignal(
        symbol="BTCUSDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=generated,
        entry_price=100.0,
        stop_price=90.0,
        target_price=120.0,
        quantity=10.0,
        risk_amount=100.0,
        confidence_score=80.0,
    )
    trade = SimulatedTrade(
        signal=signal,
        outcome=BacktestOutcome.TARGET,
        exit_time=generated + timedelta(minutes=5),
        exit_price=120.0,
        gross_pnl=200.0,
        fees=2.0,
        net_pnl=198.0,
        realized_r_multiple=1.98,
        holding_candles=5,
    )
    return HistoricalFuturesTradeResult(
        result_id=result_id,
        split=HistoricalSignalSplit.TRAIN,
        trade=trade,
    )


def test_required_margin_preserves_supported_serialized_aliases() -> None:
    payloads = (
        {
            "accepted": True,
            "decision_time": "2026-01-01T00:00:00+00:00",
            "symbol": "BTCUSDT",
            "analysis": {"position_size": {"required_margin": 125.0}},
        },
        {
            "accepted": True,
            "decision_time": "2026-01-01T00:01:00+00:00",
            "symbol": "ETHUSDT",
            "analysis": {"position_size": {"margin_required": 250.0}},
        },
        {
            "accepted": True,
            "decision_time": "2026-01-01T00:02:00+00:00",
            "symbol": "SOLUSDT",
            "analysis": {"position_size": {"margin": 375.0}},
        },
    )

    margins = _required_margin_by_key(payloads)

    assert margins[("2026-01-01T00:00:00+00:00", "BTCUSDT")] == 125.0
    assert margins[("2026-01-01T00:01:00+00:00", "ETHUSDT")] == 250.0
    assert margins[("2026-01-01T00:02:00+00:00", "SOLUSDT")] == 375.0


def test_required_margin_never_fabricates_missing_or_invalid_values() -> None:
    payloads = (
        {
            "accepted": True,
            "decision_time": "2026-01-01T00:00:00+00:00",
            "symbol": "BTCUSDT",
            "analysis": {"position_size": {"quantity": 1.0}},
        },
        {
            "accepted": True,
            "decision_time": "2026-01-01T00:01:00+00:00",
            "symbol": "ETHUSDT",
            "analysis": {"position_size": {"required_margin": -1.0}},
        },
    )

    assert _required_margin_by_key(payloads) == {}


def test_wallet_rejection_replaces_simulated_observation() -> None:
    item = _trade_result()
    isolated = HistoricalFuturesCampaignResult(
        campaign_id="campaign-1",
        starting_equity=10_000.0,
        ending_equity=10_198.0,
        observations=(
            HistoricalFuturesObservation(
                symbol="BTCUSDT",
                split=HistoricalSignalSplit.TRAIN,
                decision_time="2026-01-01T00:00:00+00:00",
                status="simulated",
            ),
        ),
        trades=(item,),
        split_metrics=(),
        rejection_counts=(),
    )

    observations = _merge_wallet_observations(
        isolated=isolated,
        missing_margin_ids=set(),
        rejected_by_id={item.result_id: "maximum_wallet_exposure"},
    )

    assert observations[0].status == "wallet_rejected"
    assert observations[0].rejection_codes == ("maximum_wallet_exposure",)


def test_missing_margin_has_explicit_rejection_code() -> None:
    item = _trade_result()
    isolated = HistoricalFuturesCampaignResult(
        campaign_id="campaign-1",
        starting_equity=10_000.0,
        ending_equity=10_198.0,
        observations=(
            HistoricalFuturesObservation(
                symbol="BTCUSDT",
                split=HistoricalSignalSplit.TRAIN,
                decision_time="2026-01-01T00:00:00+00:00",
                status="simulated",
            ),
        ),
        trades=(item,),
        split_metrics=(),
        rejection_counts=(),
    )

    observations = _merge_wallet_observations(
        isolated=isolated,
        missing_margin_ids={item.result_id},
        rejected_by_id={},
    )

    assert observations[0].rejection_codes == ("historical_required_margin_missing",)


def test_shared_manifest_preserves_base_integrity_fields() -> None:
    base = HistoricalFuturesExecutionManifest(
        campaign_id="campaign-1",
        signal_records_hash="a" * 64,
        signal_configuration_hash="b" * 64,
        result_path="result.json",
        result_hash="c" * 64,
        total_decisions=3,
        trade_count=1,
        split_counts=(("train", 3),),
    )
    manifest = SharedHistoricalFuturesExecutionManifest(
        base=base,
        wallet_configuration_hash="d" * 64,
        wallet_rejection_counts=(("maximum_wallet_exposure", 2),),
    )

    payload = manifest.to_payload()

    assert payload["signal_records_hash"] == "a" * 64
    assert payload["result_hash"] == "c" * 64
    assert payload["wallet_configuration_hash"] == "d" * 64
    assert payload["wallet_rejection_counts"] == {"maximum_wallet_exposure": 2}
