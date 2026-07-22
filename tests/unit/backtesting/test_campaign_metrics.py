from datetime import UTC, datetime, timedelta

import pytest

from apex.application.methodology_identity import METHODOLOGY_VERSION
from apex.backtesting import (
    BacktestConfig,
    BacktestRequest,
    BacktestSignal,
    HistoricalBacktestRunner,
    simulate_trade,
    summarize_trades,
)
from apex.backtesting.contracts import BacktestActivationType, BacktestOutcome
from apex.cli_commands import backtesting as backtesting_cli
from apex.cli_commands.backtesting import (
    _anchor_displaced_bars,
    _calibration_record,
    _jsonable,
    _parse_as_of,
    _report_metrics,
    _shadow_replay_signals,
)
from apex.domain.models import Candle
from apex.strategies import StrategyType, TradeDirection


def _signal() -> BacktestSignal:
    return BacktestSignal(
        symbol="BTCUSDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=1.0,
        risk_amount=2.0,
        confidence_score=70.0,
    )


def _conditional_signal(
    activation_type: BacktestActivationType = BacktestActivationType.PRICE_TOUCH,
    *,
    expiry_candles: int | None = 3,
) -> BacktestSignal:
    return BacktestSignal(
        symbol="BTCUSDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        quantity=1.0,
        risk_amount=2.0,
        confidence_score=70.0,
        activation_type=activation_type,
        activation_level=100.0,
        pre_entry_invalidation_price=98.0,
        maximum_chase_price=102.0,
        activation_expiry_candles=expiry_candles,
    )


def _candle(index: int, *, low: float, high: float, close: float) -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=5 * index)
    return Candle(
        symbol="BTCUSDT",
        timeframe="5m",
        open_time=opened,
        close_time=opened + timedelta(minutes=5),
        open=close,
        high=high,
        low=low,
        close=close,
        volume=1_000.0,
        is_closed=True,
        source="test",
    )


def test_trade_records_excursions_and_funding_drag() -> None:
    trade = simulate_trade(
        _signal(),
        (
            _candle(1, low=99.0, high=102.0, close=101.0),
            _candle(2, low=100.0, high=104.5, close=104.0),
        ),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0, funding_pct=0.1),
    )

    assert trade.metadata["maximum_favorable_excursion_r"] == pytest.approx(2.25)
    assert trade.metadata["maximum_adverse_excursion_r"] == pytest.approx(0.5)
    assert trade.metadata["actual_funding"] == pytest.approx(0.1)
    assert trade.net_pnl == pytest.approx(3.9)


def test_price_touch_conditional_replay_can_activate_and_fill_same_candle() -> None:
    trade = simulate_trade(
        _conditional_signal(),
        (
            _candle(1, low=99.5, high=101.0, close=100.5),
            _candle(2, low=100.0, high=104.5, close=104.0),
        ),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    assert trade.outcome is BacktestOutcome.TARGET
    assert trade.metadata["activation_outcome"] == "triggered"
    assert trade.metadata["activation_candle"] == 1


def test_close_trigger_waits_until_next_candle_before_entry_fill() -> None:
    trade = simulate_trade(
        _conditional_signal(BacktestActivationType.CANDLE_CLOSE),
        (
            _candle(1, low=99.0, high=101.0, close=100.5),
            _candle(2, low=99.5, high=104.5, close=104.0),
        ),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    assert trade.outcome is BacktestOutcome.TARGET
    assert trade.holding_candles == 2
    assert trade.metadata["activation_candle"] == 1


def test_conditional_replay_records_pre_entry_invalidation() -> None:
    trade = simulate_trade(
        _conditional_signal(),
        (_candle(1, low=97.5, high=99.0, close=98.5),),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    assert trade.outcome is BacktestOutcome.PRE_ENTRY_INVALIDATED
    assert trade.net_pnl == 0.0
    assert trade.metadata["activation_outcome"] == "pre_entry_invalidated"


def test_conditional_replay_records_activation_expiry() -> None:
    trade = simulate_trade(
        _conditional_signal(expiry_candles=2),
        (
            _candle(1, low=98.5, high=99.5, close=99.0),
            _candle(2, low=98.5, high=99.5, close=99.0),
        ),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    assert trade.outcome is BacktestOutcome.ACTIVATION_EXPIRED
    assert trade.metadata["activation_outcome"] == "activation_expired"


def test_conditional_replay_records_maximum_chase_breach() -> None:
    trade = simulate_trade(
        _conditional_signal(),
        (_candle(1, low=102.5, high=103.0, close=102.8),),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    assert trade.outcome is BacktestOutcome.MISSED_ENTRY
    assert trade.metadata["activation_outcome"] == "maximum_chase_breached"


def test_campaign_report_exposes_fill_and_excursion_metrics() -> None:
    filled = simulate_trade(
        _signal(),
        (_candle(1, low=99.0, high=104.5, close=104.0),),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )
    missed = simulate_trade(
        _signal(),
        (_candle(1, low=105.0, high=106.0, close=105.5),),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    report = summarize_trades((filled, missed))

    assert report.metadata["entry_fill_rate"] == pytest.approx(0.5)
    assert report.metadata["tp1_touch_count"] == 1
    assert report.metadata["average_mfe_r"] > 0

    serialized_trade = _jsonable(filled)
    metrics = _report_metrics(report)
    assert isinstance(serialized_trade, dict)
    assert serialized_trade["metadata"]["maximum_favorable_excursion_r"] > 0
    assert metrics["trades"] == []
    assert metrics["metadata"]["entry_fill_rate"] == pytest.approx(0.5)


def test_empty_report_metrics_are_explicitly_not_evaluable() -> None:
    metrics = _report_metrics(summarize_trades(()))

    assert metrics["total_trades"] == 0
    assert metrics["win_rate"] is None
    assert metrics["expectancy"] is None
    assert metrics["maximum_drawdown"] is None
    assert metrics["metadata"]["entry_fill_rate"] is None


def test_geometry_rejection_builds_diagnostic_shadow_signal() -> None:
    analysis = type(
        "Analysis",
        (),
        {
            "symbol": "BTCUSDT",
            "generated_at": datetime(2026, 1, 1, tzinfo=UTC),
            "candidate_ranking": None,
            "phase5_diagnostics": {
                "methodology_candidate_routing": {
                    "geometry_safety_audits": [
                        {
                            "candidate_id": "trend_pullback:long:0",
                            "state": "reject",
                            "diagnostics": {
                                "selected_entry": 100.0,
                                "executable_stop": 98.0,
                                "tp1_price": 104.0,
                            },
                        }
                    ]
                }
            },
        },
    )()

    signals = _shadow_replay_signals(analysis)

    assert len(signals) == 1
    assert signals[0].candidate_id == "trend_pullback:long:0"
    assert signals[0].replay_source == "geometry_rejected"


def test_replay_records_full_forward_path_excursion_and_direction() -> None:
    trade = simulate_trade(
        _signal(),
        (_candle(1, low=99.0, high=105.0, close=103.0),),
        config=BacktestConfig(fee_pct=0.0, slippage_pct=0.0),
    )

    assert trade.metadata["counterfactual_path_mfe_r"] == pytest.approx(2.5)
    assert trade.metadata["counterfactual_path_mae_r"] == pytest.approx(0.5)
    assert trade.metadata["direction_correct_at_horizon"] is True


def test_as_of_parser_requires_timezone_and_normalizes_utc() -> None:
    parsed = _parse_as_of("2026-01-01T05:00:00+05:00")

    assert parsed == datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="timezone"):
        _parse_as_of("2026-01-01T00:00:00")


def test_anchor_displacement_covers_historical_gap() -> None:
    fetch_time = datetime(2026, 1, 2, tzinfo=UTC)
    anchor_time = datetime(2026, 1, 1, 12, tzinfo=UTC)

    assert (
        _anchor_displaced_bars(
            timeframe="5m",
            anchor_time=anchor_time,
            fetch_time=fetch_time,
        )
        == 146
    )


def test_chronological_backtest_report_records_methodology_version() -> None:
    request = BacktestRequest(
        signals=(_signal(),),
        candles_by_symbol={"BTCUSDT": (_candle(1, low=99.0, high=104.5, close=104.0),)},
    )

    study = HistoricalBacktestRunner().run(request)

    assert request.methodology_version == METHODOLOGY_VERSION
    assert study.report.metadata["methodology_version"] == METHODOLOGY_VERSION


def test_calibration_record_preserves_zero_trade_and_methodology_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        backtesting_cli,
        "serialize_symbol_analysis",
        lambda _analysis: {
            "symbol": "BTCUSDT",
            "generated_at": "2026-07-18T12:00:00+00:00",
            "decision": "NO_TRADE",
            "reasons": ["candidate selection produced no setup"],
            "setup": None,
            "phase5_diagnostics": {
                "zero_trade_diagnostics": {"decision": "NO_TRADE"},
                "methodology_candidate_routing": {
                    "mode": "shadow",
                    "suppressed_candidate_count": 0,
                    "suppressed_strategies": [],
                    "reason_codes": ["METHODOLOGY_CANDIDATE_ROUTING_SHADOW"],
                },
            },
        },
    )

    record = _calibration_record(analysis=object(), partition="validation")

    assert record["production_decision"] == "NO_TRADE"
    assert record["methodology_gate_mode"] == "shadow"
    assert record["zero_trade_diagnostics"] == {"decision": "NO_TRADE"}
    assert record["entry_geometry"] is None
