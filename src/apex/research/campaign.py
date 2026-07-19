"""Resumable, checksum-verified Binance public-data campaign importer."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from apex.domain.models import Candle

PUBLIC_DATA_BASE = "https://data.binance.vision/data/futures/um/monthly"
PUBLIC_DATA_BUCKET = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"


@dataclass(frozen=True, slots=True)
class CampaignConfig:
    dataset_dir: Path = Path("data/research/binance_um")
    months: int = 24
    universe_size: int = 30
    source_timeframe: str = "1m"
    data_types: tuple[str, ...] = ("klines", "fundingRate", "aggTrades")

    def __post_init__(self) -> None:
        if self.months < 1 or self.universe_size < 1:
            raise ValueError("campaign months and universe size must be positive")
        if self.source_timeframe != "1m":
            raise ValueError("production campaign source timeframe must be 1m")
        if not self.data_types or any(
            item not in {"klines", "fundingRate", "aggTrades"} for item in self.data_types
        ):
            raise ValueError("campaign data types must use supported Binance public archives")


@dataclass(frozen=True, slots=True)
class ArchiveSpec:
    symbol: str
    month: str
    data_type: str = "klines"
    timeframe: str | None = "1m"

    @property
    def filename(self) -> str:
        if self.data_type == "klines":
            return f"{self.symbol}-{self.timeframe}-{self.month}.zip"
        return f"{self.symbol}-{self.data_type}-{self.month}.zip"

    @property
    def relative_url(self) -> str:
        if self.data_type == "klines":
            return f"klines/{self.symbol}/{self.timeframe}/{self.filename}"
        return f"{self.data_type}/{self.symbol}/{self.filename}"


@dataclass(frozen=True, slots=True)
class CampaignManifest:
    schema_version: int
    created_at: str
    complete_months: tuple[str, ...]
    universe_by_month: Mapping[str, tuple[str, ...]]
    files: Mapping[str, str]
    missing: Mapping[str, str]

    @property
    def checksum(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


def latest_complete_utc_months(as_of: datetime, count: int = 24) -> tuple[str, ...]:
    """Return oldest-to-newest complete UTC months; the active month is excluded."""

    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("campaign timestamp must be timezone-aware")
    if count < 1:
        raise ValueError("month count must be positive")
    year, month = as_of.astimezone(UTC).year, as_of.astimezone(UTC).month
    result: list[str] = []
    for _ in range(count):
        month -= 1
        if month == 0:
            year -= 1
            month = 12
        result.append(f"{year:04d}-{month:02d}")
    return tuple(reversed(result))


def point_in_time_universe(
    trailing_quote_volume: Mapping[str, float],
    eligible_symbols: Iterable[str],
    *,
    limit: int = 30,
) -> tuple[str, ...]:
    """Select only symbols eligible at that month boundary using trailing volume."""

    eligible = {symbol.upper() for symbol in eligible_symbols if symbol.upper().endswith("USDT")}
    ranked = sorted(
        (
            (symbol.upper(), volume)
            for symbol, volume in trailing_quote_volume.items()
            if symbol.upper() in eligible and volume >= 0
        ),
        key=lambda item: (-item[1], item[0]),
    )
    return tuple(symbol for symbol, _ in ranked[:limit])


class PublicDataImporter:
    """Download one archive at a time with resume-by-presence and SHA-256 integrity."""

    def __init__(self, config: CampaignConfig, *, client: httpx.Client | None = None) -> None:
        self.config = config
        self._client = client or httpx.Client(timeout=60.0, follow_redirects=True)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> PublicDataImporter:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def download(self, spec: ArchiveSpec) -> tuple[Path, str]:
        target = self.config.dataset_dir / spec.relative_url
        target.parent.mkdir(parents=True, exist_ok=True)
        checksum_url = f"{PUBLIC_DATA_BASE}/{spec.relative_url}.CHECKSUM"
        expected = self._fetch_checksum(checksum_url)
        if target.exists() and sha256_file(target) == expected:
            return target, expected

        partial = target.with_suffix(target.suffix + ".part")
        url = f"{PUBLIC_DATA_BASE}/{spec.relative_url}"
        with self._client.stream("GET", url) as response:
            response.raise_for_status()
            with partial.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
        actual = sha256_file(partial)
        if actual != expected:
            partial.unlink(missing_ok=True)
            raise ValueError(f"checksum mismatch for {spec.filename}: {actual} != {expected}")
        os.replace(partial, target)
        return target, expected

    def _fetch_checksum(self, url: str) -> str:
        response = self._client.get(url)
        response.raise_for_status()
        value = response.text.strip().split()[0].lower()
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("invalid Binance CHECKSUM response")
        return value

    def list_kline_symbols(self) -> tuple[str, ...]:
        """List historical USD-M kline symbol prefixes from Binance's public bucket."""

        prefix = "data/futures/um/monthly/klines/"
        continuation: str | None = None
        symbols: set[str] = set()
        while True:
            params = {"list-type": "2", "prefix": prefix, "delimiter": "/"}
            if continuation is not None:
                params["continuation-token"] = continuation
            response = self._client.get(PUBLIC_DATA_BUCKET, params=params)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            namespace = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
            for item in root.findall("s3:CommonPrefixes/s3:Prefix", namespace):
                value = (item.text or "").removeprefix(prefix).strip("/")
                if value.endswith("USDT"):
                    symbols.add(value)
            truncated = root.findtext("s3:IsTruncated", default="false", namespaces=namespace)
            if truncated.lower() != "true":
                break
            continuation = root.findtext(
                "s3:NextContinuationToken", default="", namespaces=namespace
            )
            if not continuation:
                raise ValueError("truncated Binance bucket listing omitted continuation token")
        return tuple(sorted(symbols))

    def build_dynamic_universe(
        self, months: tuple[str, ...], *, limit: int = 30
    ) -> tuple[dict[str, tuple[str, ...]], dict[str, str]]:
        """Rank month M using M-1 quote volume and only markets active at M's open."""

        symbols = self.list_kline_symbols()
        universes: dict[str, tuple[str, ...]] = {}
        missing: dict[str, str] = {}
        for month in months:
            previous = _previous_month(month)
            trailing_volume: dict[str, float] = {}
            eligible: list[str] = []
            month_open = datetime.fromisoformat(f"{month}-01T00:00:00+00:00")
            for symbol in symbols:
                try:
                    previous_path, _ = self.download(ArchiveSpec(symbol, previous, timeframe="1d"))
                    current_path, _ = self.download(ArchiveSpec(symbol, month, timeframe="1d"))
                    previous_candles = read_kline_archive(
                        previous_path, symbol=symbol, timeframe="1d"
                    )
                    current_candles = read_kline_archive(
                        current_path, symbol=symbol, timeframe="1d"
                    )
                except (httpx.HTTPError, OSError, ValueError, zipfile.BadZipFile) as exc:
                    missing[f"{month}:{symbol}:universe"] = f"{type(exc).__name__}: {exc}"
                    continue
                if not current_candles or current_candles[0].open_time > month_open:
                    continue
                eligible.append(symbol)
                trailing_volume[symbol] = sum(
                    candle.quote_volume or 0.0 for candle in previous_candles
                )
            universes[month] = point_in_time_universe(trailing_volume, eligible, limit=limit)
        return universes, missing


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_kline_archive(path: Path, *, symbol: str, timeframe: str = "1m") -> tuple[Candle, ...]:
    """Parse a verified Binance kline ZIP deterministically, tolerating an optional header."""

    candles: list[Candle] = []
    with zipfile.ZipFile(path) as archive:
        csv_names = sorted(name for name in archive.namelist() if name.lower().endswith(".csv"))
        if len(csv_names) != 1:
            raise ValueError("kline archive must contain exactly one CSV")
        with archive.open(csv_names[0]) as raw:
            rows = csv.reader(line.decode("utf-8") for line in raw)
            for row in rows:
                if not row or not row[0].isdigit():
                    continue
                candles.append(
                    Candle(
                        symbol=symbol.upper(),
                        timeframe=timeframe,
                        open_time=datetime.fromtimestamp(int(row[0]) / 1000, tz=UTC),
                        close_time=datetime.fromtimestamp(int(row[6]) / 1000, tz=UTC),
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]),
                        quote_volume=float(row[7]),
                        trade_count=int(row[8]),
                        taker_buy_base_volume=float(row[9]),
                        taker_buy_quote_volume=float(row[10]),
                        is_closed=True,
                        source="binance-public-data",
                    )
                )
    ordered = tuple(sorted(candles, key=lambda candle: candle.open_time))
    if len({candle.open_time for candle in ordered}) != len(ordered):
        raise ValueError("kline archive contains duplicate open timestamps")
    return ordered


def write_manifest(path: Path, manifest: CampaignManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def default_campaign_manifest(
    universe_by_month: Mapping[str, tuple[str, ...]], *, as_of: datetime | None = None
) -> CampaignManifest:
    timestamp = as_of or datetime.now(UTC)
    return CampaignManifest(
        schema_version=1,
        created_at=timestamp.isoformat(),
        complete_months=latest_complete_utc_months(timestamp),
        universe_by_month=dict(universe_by_month),
        files={},
        missing={},
    )


def _previous_month(value: str) -> str:
    year, month = (int(item) for item in value.split("-"))
    month -= 1
    if month == 0:
        year -= 1
        month = 12
    return f"{year:04d}-{month:02d}"


__all__ = [
    "ArchiveSpec",
    "CampaignConfig",
    "CampaignManifest",
    "PublicDataImporter",
    "default_campaign_manifest",
    "latest_complete_utc_months",
    "point_in_time_universe",
    "read_kline_archive",
    "sha256_file",
    "write_manifest",
]
