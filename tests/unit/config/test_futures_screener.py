from apex.config.futures_screener import FuturesScreenerSettings


def test_universe_settings_are_normalized() -> None:
    settings = FuturesScreenerSettings(
        quote_asset=" usdt ",
        blacklist=("btcusdt", "ETH/USDT"),
        allowlist=("solusdt",),
        metadata_cache_ttl_seconds=900,
    )

    assert settings.quote_asset == "USDT"
    assert settings.blacklist == ("BTCUSDT", "ETH/USDT")
    assert settings.allowlist == ("SOLUSDT",)
    assert settings.metadata_cache_ttl_seconds == 900
