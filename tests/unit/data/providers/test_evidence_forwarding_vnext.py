from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from apex.data.cache.candles import FileCandleCache
from apex.data.providers.cached import CachedMarketDataProvider
from apex.data.providers.resampled import ResamplingMarketDataProvider
from apex.domain.futures_evidence import FundingRateSnapshot, PremiumIndexSnapshot

NOW = datetime(2026, 7, 18, tzinfo=UTC)


class Provider:
    name = "fixture"

    def fetch_funding_rates(self, symbol: str, limit: int = 100) -> tuple[FundingRateSnapshot, ...]:
        return (FundingRateSnapshot(symbol, 0.001, NOW, self.name),)

    def fetch_premium_index(self, symbol: str) -> PremiumIndexSnapshot:
        return PremiumIndexSnapshot(symbol, 101, 100, 0.001, None, NOW, self.name)


def test_cache_and_resampling_decorators_forward_futures_evidence(tmp_path: Path) -> None:
    cached = CachedMarketDataProvider(Provider(), FileCandleCache(tmp_path))  # type: ignore[arg-type]
    resampled = ResamplingMarketDataProvider(cached, resampling_sources={})  # type: ignore[arg-type]

    assert resampled.fetch_funding_rates("BTCUSDT")[0].funding_rate == 0.001
    assert resampled.fetch_premium_index("BTCUSDT").basis_percentage == 1.0
