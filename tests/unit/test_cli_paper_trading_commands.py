from __future__ import annotations

from typing import Any

import typer
from typer.testing import CliRunner

from apex.cli_commands import paper_trading


def _paper_app() -> typer.Typer:
    app = typer.Typer()
    paper_trading.register_paper_trading_commands(app)
    return app


def test_paper_record_normalizes_compact_symbol(monkeypatch: Any) -> None:
    captured: dict[str, object] = {}

    def fake_record(symbol: str, candle_limit: int) -> None:
        captured.update(symbol=symbol, candle_limit=candle_limit)

    monkeypatch.setattr(paper_trading, "legacy_paper_record", fake_record)

    result = CliRunner().invoke(_paper_app(), ["record", "1000PEPEUSDT", "--candles", "320"])

    assert result.exit_code == 0, result.output
    assert captured == {"symbol": "1000PEPE/USDT", "candle_limit": 320}


def test_paper_update_normalizes_optional_symbol_filter(monkeypatch: Any) -> None:
    captured: dict[str, object] = {}

    def fake_update(symbol: str | None, timeframe: str, candle_limit: int) -> None:
        captured.update(symbol=symbol, timeframe=timeframe, candle_limit=candle_limit)

    monkeypatch.setattr(paper_trading, "legacy_paper_update", fake_update)

    result = CliRunner().invoke(
        _paper_app(),
        ["update", "BTCUSDT", "--timeframe", "15m", "--candles", "120"],
    )

    assert result.exit_code == 0, result.output
    assert captured == {"symbol": "BTC/USDT", "timeframe": "15m", "candle_limit": 120}


def test_paper_update_without_symbol_preserves_all_trade_mode(monkeypatch: Any) -> None:
    captured: dict[str, object] = {}

    def fake_update(symbol: str | None, timeframe: str, candle_limit: int) -> None:
        captured.update(symbol=symbol, timeframe=timeframe, candle_limit=candle_limit)

    monkeypatch.setattr(paper_trading, "legacy_paper_update", fake_update)

    result = CliRunner().invoke(_paper_app(), ["update"])

    assert result.exit_code == 0, result.output
    assert captured == {"symbol": None, "timeframe": "5m", "candle_limit": 80}
