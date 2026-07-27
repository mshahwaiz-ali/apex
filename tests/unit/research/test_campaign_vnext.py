from __future__ import annotations

import hashlib
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from apex.research.campaign import (
    ArchiveSpec,
    CampaignConfig,
    CampaignManifest,
    PublicDataImporter,
    aggregate_taker_flow,
    latest_complete_utc_months,
    point_in_time_universe,
    read_aggregate_trade_archive,
    read_funding_rate_archive,
    read_historical_metrics_archive,
    read_kline_archive,
)


def test_latest_campaign_excludes_active_utc_month() -> None:
    months = latest_complete_utc_months(datetime(2026, 7, 19, tzinfo=UTC), 3)
    assert months == ("2026-04", "2026-05", "2026-06")


def test_point_in_time_universe_is_volume_ranked_and_eligibility_bounded() -> None:
    result = point_in_time_universe(
        {"AAAUSDT": 10, "BBBUSDT": 30, "CCCUSDT": 20, "OLDUSDT": 100},
        ("AAAUSDT", "BBBUSDT", "CCCUSDT"),
        limit=2,
    )
    assert result == ("BBBUSDT", "CCCUSDT")


def test_campaign_dataset_fingerprint_excludes_creation_timestamp() -> None:
    first = CampaignManifest(
        schema_version=2,
        created_at="2026-07-27T00:00:00+00:00",
        complete_months=("2026-06",),
        universe_by_month={"2026-06": ("BTCUSDT",)},
        files={"funding.zip": "a" * 64},
        missing={},
    )
    second = CampaignManifest(
        schema_version=2,
        created_at="2026-07-28T00:00:00+00:00",
        complete_months=first.complete_months,
        universe_by_month=first.universe_by_month,
        files=first.files,
        missing=first.missing,
    )

    assert first.checksum == second.checksum


def test_importer_verifies_checksum_and_resumes(tmp_path: Path) -> None:
    body = b"verified archive"
    digest = hashlib.sha256(body).hexdigest()
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return (
            httpx.Response(200, text=f"{digest}  file.zip")
            if str(request.url).endswith("CHECKSUM")
            else httpx.Response(200, content=body)
        )

    spec = ArchiveSpec("BTCUSDT", "2026-06")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        importer = PublicDataImporter(CampaignConfig(dataset_dir=tmp_path), client=client)
        first, _ = importer.download(spec)
        second, _ = importer.download(spec)

    assert first == second
    assert first.read_bytes() == body
    assert sum(not call.endswith("CHECKSUM") for call in calls) == 1


def test_kline_archive_keeps_participation_columns(tmp_path: Path) -> None:
    archive = tmp_path / "BTCUSDT-1m-2026-06.zip"
    row = "0,100,102,99,101,10,59999,1005,7,6,603,0\n"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("BTCUSDT-1m-2026-06.csv", row)

    candles = read_kline_archive(archive, symbol="BTCUSDT")
    assert candles[0].quote_volume == 1005
    assert candles[0].trade_count == 7
    assert candles[0].taker_buy_quote_volume == 603


def test_funding_archive_preserves_event_time_rate_and_interval(tmp_path: Path) -> None:
    archive = tmp_path / "BTCUSDT-fundingRate-2026-06.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(
            "BTCUSDT-fundingRate-2026-06.csv",
            "calc_time,funding_interval_hours,last_funding_rate\n1780272000000,8,0.00010000\n",
        )

    observations = read_funding_rate_archive(archive, symbol="BTCUSDT")

    assert observations[0].funding_time == datetime(2026, 6, 1, tzinfo=UTC)
    assert observations[0].funding_interval_hours == 8
    assert observations[0].funding_rate == 0.0001


def test_aggregate_trade_archive_builds_closed_taker_flow_buckets(tmp_path: Path) -> None:
    archive = tmp_path / "BTCUSDT-aggTrades-2026-06.zip"
    start = datetime(2026, 6, 1, tzinfo=UTC)
    first_ms = int(start.timestamp() * 1000)
    second_ms = int((start + timedelta(minutes=1)).timestamp() * 1000)
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(
            "BTCUSDT-aggTrades-2026-06.csv",
            "agg_trade_id,price,quantity,first_trade_id,last_trade_id,"
            "transact_time,is_buyer_maker\n"
            f"1,100,2,1,1,{first_ms},false\n"
            f"2,100,1,2,2,{second_ms},true\n",
        )

    trades = read_aggregate_trade_archive(archive, symbol="BTCUSDT")
    flow = aggregate_taker_flow(trades, period=timedelta(minutes=5))

    assert len(flow) == 1
    assert flow[0].buy_volume == 200
    assert flow[0].sell_volume == 100
    assert flow[0].buy_sell_ratio == 2


def test_daily_metrics_archive_preserves_open_interest_and_ratio_lineage(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "BTCUSDT-metrics-2026-07-25.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(
            "BTCUSDT-metrics-2026-07-25.csv",
            "create_time,symbol,sum_open_interest,sum_open_interest_value,"
            "count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,"
            "count_long_short_ratio,sum_taker_long_short_vol_ratio\n"
            "2026-07-25 00:00:00,BTCUSDT,106063.291,6802591901.1961,"
            "2.0215,1.6639,1.8666,1.3947\n",
        )

    observations = read_historical_metrics_archive(archive, symbol="BTCUSDT")

    assert observations[0].captured_at == datetime(2026, 7, 25, tzinfo=UTC)
    assert observations[0].open_interest == 106063.291
    assert observations[0].taker_long_short_volume_ratio == 1.3947
    assert observations[0].as_open_interest().period == "5m"
    assert (
        ArchiveSpec(
            "BTCUSDT",
            "2026-07-25",
            data_type="metrics",
            timeframe=None,
        ).public_base_url
        == "https://data.binance.vision/data/futures/um/daily"
    )
