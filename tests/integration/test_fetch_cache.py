from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

import apex.cli
from apex.cli import app
from apex.domain.models import Candle

runner = CliRunner()


class FakeBinanceMarketDataProvider:
    """Context-managed fake matching the Binance provider surface."""

    candle_calls = 0
    name = "binance"

    def __enter__(self) -> "FakeBinanceMarketDataProvider":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        type(self).candle_calls += 1

        return [
            Candle(
                symbol=symbol.upper(),
                timeframe=timeframe,
                open_time=datetime(2026, 7, 12, 11, 30, tzinfo=UTC),
                close_time=datetime(2026, 7, 12, 11, 45, tzinfo=UTC),
                open=100.0,
                high=110.0,
                low=95.0,
                close=105.0,
                volume=123.45,
                is_closed=True,
                source=self.name,
            )
        ][:limit]


def test_fetch_command_reuses_fresh_file_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    config_dir.mkdir()

    (config_dir / "default.yaml").write_text(
        "environment: test\n"
        "log_level: INFO\n"
        f"data_dir: {data_dir}\n"
        f"log_dir: {tmp_path / 'logs'}\n"
        "cache_enabled: true\n"
        "analysis_timeframes: [5m, 15m, 30m, 1h, 4h]\n",
        encoding="utf-8",
    )

    FakeBinanceMarketDataProvider.candle_calls = 0

    monkeypatch.setenv("APEX_CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(
        apex.cli,
        "BinanceMarketDataProvider",
        FakeBinanceMarketDataProvider,
    )

    first = runner.invoke(
        app,
        ["fetch", "BTC/USDT", "--timeframe", "15m", "--limit", "1"],
    )
    second = runner.invoke(
        app,
        ["fetch", "BTC/USDT", "--timeframe", "15m", "--limit", "1"],
    )

    assert first.exit_code == 0, first.stdout
    assert second.exit_code == 0, second.stdout
    assert first.stdout == second.stdout
    assert FakeBinanceMarketDataProvider.candle_calls == 1

    cache_files = list((data_dir / "cache" / "candles").glob("*.json"))
    assert len(cache_files) == 1
