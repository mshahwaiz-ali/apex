import pytest

from apex.cli_commands.backtesting import _aligned_history_limit


@pytest.mark.parametrize(
    ("timeframe", "expected"),
    [
        ("1m", 4200),
        ("3m", 1534),
        ("5m", 1000),
        ("15m", 467),
        ("30m", 334),
        ("1h", 267),
        ("4h", 217),
    ],
)
def test_aligned_history_limit_covers_full_five_minute_replay_horizon(
    timeframe: str,
    expected: int,
) -> None:
    assert (
        _aligned_history_limit(
            timeframe=timeframe,
            replay_timeframe="5m",
            replay_history_candles=1000,
            analysis_candles=200,
        )
        == expected
    )


def test_aligned_history_limit_rejects_live_request_above_provider_limit() -> None:
    with pytest.raises(
        ValueError,
        match="exceeding the 10000 candle live-provider limit",
    ):
        _aligned_history_limit(
            timeframe="1m",
            replay_timeframe="4h",
            replay_history_candles=1000,
            analysis_candles=200,
        )


def test_aligned_history_limit_rejects_history_shorter_than_warmup() -> None:
    with pytest.raises(
        ValueError,
        match="greater than or equal to analysis candles",
    ):
        _aligned_history_limit(
            timeframe="5m",
            replay_timeframe="5m",
            replay_history_candles=100,
            analysis_candles=200,
        )
