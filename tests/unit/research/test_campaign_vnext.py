from __future__ import annotations

import hashlib
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx

from apex.research.campaign import (
    ArchiveSpec,
    CampaignConfig,
    PublicDataImporter,
    latest_complete_utc_months,
    point_in_time_universe,
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
