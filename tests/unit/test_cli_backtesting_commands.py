from __future__ import annotations

from typing import Any

import typer
from typer.testing import CliRunner

from apex.cli_commands import backtesting


def test_simulate_current_setup_normalizes_compact_symbol(monkeypatch: Any) -> None:
    captured: dict[str, object] = {}

    def fake_legacy_simulation(
        symbol: str,
        output: str,
        candle_limit: int,
        replay_timeframe: str,
    ) -> None:
        captured.update(
            symbol=symbol,
            output=output,
            candle_limit=candle_limit,
            replay_timeframe=replay_timeframe,
        )

    monkeypatch.setattr(
        backtesting,
        "legacy_simulate_current_setup",
        fake_legacy_simulation,
    )
    app = typer.Typer()
    backtesting.register_backtesting_commands(app)

    result = CliRunner().invoke(
        app,
        [
            "simulate-current-setup",
            "BTCUSDT",
            "--output",
            "json",
            "--candles",
            "320",
            "--replay-timeframe",
            "15m",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured == {
        "symbol": "BTC/USDT",
        "output": "json",
        "candle_limit": 320,
        "replay_timeframe": "15m",
    }
