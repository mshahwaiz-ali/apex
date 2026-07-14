from datetime import UTC, datetime, timedelta

from apex.application.analysis import SymbolAnalysis
from apex.application.chronological_backtest import (
    ChronologicalBacktestRequest,
    run_chronological_pipeline_backtest,
)
from apex.domain import Candle
from apex.risk import RiskAssessment, RiskDecision, RiskRejectionCode

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _candles(count: int) -> tuple[Candle, ...]:
    return tuple(
        Candle(
            symbol="BTC/USDT",
            timeframe="5m",
            open_time=NOW + timedelta(minutes=5 * index),
            close_time=NOW + timedelta(minutes=5 * (index + 1)),
            open=100.0 + index * 0.01,
            high=101.0 + index * 0.01,
            low=99.0 + index * 0.01,
            close=100.5 + index * 0.01,
            volume=100.0,
            is_closed=True,
            source="fixture",
        )
        for index in range(count)
    )


def test_chronological_runner_passes_only_prefix_candles(monkeypatch) -> None:
    captured_lengths: list[int] = []

    def fake_analyze_symbol(
        symbol,
        provider,
        *,
        timeframes,
        candle_limit,
        risk_config,
        generated_at,
        strategy_routing,
        gainer_state_thresholds,
    ):
        assert strategy_routing is None
        assert gainer_state_thresholds is None
        candles = provider.fetch_candles(symbol, "5m", limit=candle_limit)
        assert len(candles) == candle_limit
        assert all(candle.close_time <= generated_at for candle in candles)
        assert candles[-1].close_time == generated_at
        captured_lengths.append(len(candles))
        return SymbolAnalysis(
            symbol=symbol,
            generated_at=generated_at,
            assessment=RiskAssessment(
                symbol=symbol,
                decision_time=generated_at,
                decision=RiskDecision.REJECTED,
                setup=None,
                rejection_codes=(RiskRejectionCode.NO_SELECTED_CANDIDATE,),
                reasons=("no selected candidate in fixture",),
                configuration_id="test",
            ),
            candidate_count=0,
            evaluated_timeframes=tuple(timeframes),
            regime_by_timeframe={},
            data_quality_by_timeframe={},
        )

    monkeypatch.setattr(
        "apex.application.chronological_backtest.analyze_symbol",
        fake_analyze_symbol,
    )

    result = run_chronological_pipeline_backtest(
        ChronologicalBacktestRequest(
            symbol="BTC/USDT",
            candles_by_timeframe={"5m": _candles(45)},
            analysis_timeframes=("5m",),
            replay_timeframe="5m",
            candle_limit=40,
        )
    )

    assert result.decision_count == 5
    assert result.skipped_count == 5
    assert result.approved_count == 0
    assert result.candidate_count_distribution == {"0": 5, "1": 0, "2_plus": 0}
    assert result.rejection_code_counts == {"no_selected_candidate": 5}
    assert result.rejection_reason_counts == {
        "no selected candidate in fixture": 5,
    }
    assert result.skipped_by_stage == {
        "insufficient_warmup": 0,
        "no_candidates": 5,
        "risk_rejected": 5,
        "cooldown": 0,
        "overlap": 0,
        "no_future_candles": 0,
    }
    assert result.phase5_outcome_counts == {}
    assert result.phase5_reason_counts == {}
    assert result.phase5_strategy_counts == {}
    assert result.phase5_score_bands == {
        "below_40": 0,
        "40_to_49_99": 0,
        "50_to_59_99": 0,
        "60_to_69_99": 0,
        "70_plus": 0,
    }
    assert captured_lengths == [40, 40, 40, 40, 40]
