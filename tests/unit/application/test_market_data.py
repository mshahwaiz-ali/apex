from pathlib import Path

import pytest

from apex.application.market_data import create_market_data_services
from apex.config import FileSettings
from apex.data.providers import CachedMarketDataProvider, ResamplingMarketDataProvider
from apex.domain.models import Candle, TickerSnapshot


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> list[Candle]:
        raise AssertionError("not needed in construction tests")

    def fetch_ticker(self, symbol: str) -> TickerSnapshot:
        raise AssertionError("not needed in construction tests")


def make_settings(tmp_path: Path, *, cache_enabled: bool) -> FileSettings:
    return FileSettings(
        data_dir=tmp_path,
        log_dir=tmp_path / "logs",
        cache_enabled=cache_enabled,
        timeframe_resampling_sources={},
    )


def test_builds_cached_candles_and_live_ticker(tmp_path: Path) -> None:
    provider = FakeProvider()

    services = create_market_data_services(
        make_settings(tmp_path, cache_enabled=True),
        provider_name="fake",
        provider_builders={"fake": lambda: provider},
    )

    assert isinstance(services.candles, CachedMarketDataProvider)
    assert services.ticker is provider

    services.close()
    assert provider.closed is True


def test_disabling_cache_reuses_live_provider(tmp_path: Path) -> None:
    provider = FakeProvider()

    with create_market_data_services(
        make_settings(tmp_path, cache_enabled=False),
        provider_name="fake",
        provider_builders={"fake": lambda: provider},
    ) as services:
        assert services.candles is provider
        assert services.ticker is provider

    assert provider.closed is True


def test_builds_resampling_candles_when_configured(tmp_path: Path) -> None:
    provider = FakeProvider()

    services = create_market_data_services(
        FileSettings(
            data_dir=tmp_path,
            log_dir=tmp_path / "logs",
            cache_enabled=False,
            timeframe_resampling_sources={"1D": "4h"},
        ),
        provider_name="fake",
        provider_builders={"fake": lambda: provider},
    )

    assert isinstance(services.candles, ResamplingMarketDataProvider)
    assert services.ticker is provider

    services.close()
    assert provider.closed is True


def test_rejects_unknown_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported market-data provider"):
        create_market_data_services(
            make_settings(tmp_path, cache_enabled=True),
            provider_name="missing",
            provider_builders={"fake": FakeProvider},
        )
