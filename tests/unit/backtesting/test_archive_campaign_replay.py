from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.backtesting.historical_signal_replay import HistoricalCandleSeries
from apex.cli_commands.backtesting import (
    _archive_campaign_series,
    _campaign_decision_times,
)
from apex.domain.models import Candle
from apex.research.campaign import (
    read_verified_campaign_funding,
    read_verified_campaign_klines,
    read_verified_campaign_resampled_klines,
)


def _write_archive(
    dataset_dir: Path,
    *,
    relative_path: str,
    csv_name: str,
    content: str,
) -> str:
    path = dataset_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(csv_name, content)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_campaign_archive_loaders_require_manifest_checksums(tmp_path: Path) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    for index in range(10):
        opened = start + timedelta(minutes=index)
        rows.append(
            ",".join(
                (
                    str(int(opened.timestamp() * 1000)),
                    "100",
                    "102",
                    "99",
                    "101",
                    "10",
                    str(int((opened + timedelta(minutes=1)).timestamp() * 1000) - 1),
                    "1005",
                    "7",
                    "6",
                    "603",
                    "0",
                )
            )
        )
    kline_relative = "klines/BTCUSDT/1m/BTCUSDT-1m-2026-01.zip"
    funding_relative = "fundingRate/BTCUSDT/BTCUSDT-fundingRate-2026-01.zip"
    files = {
        kline_relative: _write_archive(
            tmp_path,
            relative_path=kline_relative,
            csv_name="BTCUSDT-1m-2026-01.csv",
            content="\n".join(rows) + "\n",
        ),
        funding_relative: _write_archive(
            tmp_path,
            relative_path=funding_relative,
            csv_name="BTCUSDT-fundingRate-2026-01.csv",
            content=(
                "calc_time,funding_interval_hours,last_funding_rate\n1767225600000,8,0.0001\n"
            ),
        ),
    }
    (tmp_path / "campaign_manifest.json").write_text(
        json.dumps({"files": files}),
        encoding="utf-8",
    )

    candles = read_verified_campaign_klines(tmp_path, symbol="BTC/USDT")
    five_minute = read_verified_campaign_resampled_klines(
        tmp_path,
        symbol="BTC/USDT",
        target_timeframe="5m",
    )
    funding = read_verified_campaign_funding(tmp_path, symbol="BTC/USDT")

    assert len(candles) == 10
    assert len(five_minute) == 2
    assert candles[0].symbol == "BTC/USDT"
    assert funding[0].symbol == "BTC/USDT"

    kline_path = tmp_path / kline_relative
    kline_path.write_bytes(kline_path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="checksum mismatch"):
        read_verified_campaign_klines(tmp_path, symbol="BTC/USDT")


def test_full_range_decisions_cover_usable_archive_without_future_windows() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles = tuple(
        Candle(
            symbol="BTC/USDT",
            timeframe="5m",
            open_time=start + timedelta(minutes=5 * index),
            close_time=start + timedelta(minutes=5 * (index + 1)),
            open=100,
            high=102,
            low=99,
            close=101,
            volume=10,
            is_closed=True,
            source="fixture",
        )
        for index in range(100)
    )
    replay = HistoricalCandleSeries(
        symbol="BTC/USDT",
        timeframe="5m",
        candles=candles,
    )

    decisions = _campaign_decision_times(
        series=(replay,),
        replay_series=replay,
        candle_limit=20,
        replay_candles=10,
        decision_points=5,
        sample_full_range=True,
    )

    assert decisions[0] == candles[19].close_time
    assert decisions[-1] == candles[-11].close_time
    assert decisions == tuple(sorted(decisions))
    assert len(set(decisions)) == 5


def test_archive_series_resamples_one_minute_campaign(tmp_path: Path) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    for index in range(15):
        opened = start + timedelta(minutes=index)
        rows.append(
            f"{int(opened.timestamp() * 1000)},100,102,99,101,10,"
            f"{int((opened + timedelta(minutes=1)).timestamp() * 1000) - 1},"
            "1005,7,6,603,0"
        )
    relative = "klines/BTCUSDT/1m/BTCUSDT-1m-2026-01.zip"
    checksum = _write_archive(
        tmp_path,
        relative_path=relative,
        csv_name="BTCUSDT-1m-2026-01.csv",
        content="\n".join(rows) + "\n",
    )
    (tmp_path / "campaign_manifest.json").write_text(
        json.dumps({"files": {relative: checksum}}),
        encoding="utf-8",
    )

    series = _archive_campaign_series(
        archive_dataset_dir=tmp_path,
        symbol="BTC/USDT",
        timeframes=("1m", "5m", "15m"),
        anchor_time=None,
    )

    assert [len(item.candles) for item in series] == [15, 3, 1]
    assert all(candle.is_closed for item in series for candle in item.candles)
