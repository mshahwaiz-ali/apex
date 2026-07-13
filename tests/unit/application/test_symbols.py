import pytest

from apex.application.symbols import normalize_market_symbol


def test_normalizes_slashed_symbol() -> None:
    assert normalize_market_symbol(" btc/usdt ") == "BTC/USDT"


def test_normalizes_compact_symbol() -> None:
    assert normalize_market_symbol("btcusdt") == "BTC/USDT"


def test_preserves_numeric_base_prefix() -> None:
    assert normalize_market_symbol("1000pepeusdt") == "1000PEPE/USDT"


def test_accepts_provider_specific_asset_characters() -> None:
    assert normalize_market_symbol("abc-2/usdt") == "ABC-2/USDT"


@pytest.mark.parametrize(
    "value",
    (
        "",
        "BTC/",
        "/USDT",
        "BTC/USDT/PERP",
        "BTC@/USDT",
        "USDT/USDT",
    ),
)
def test_rejects_invalid_symbols(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_market_symbol(value)


def test_unusual_compact_quote_requires_explicit_form() -> None:
    with pytest.raises(ValueError, match="BASE/QUOTE"):
        normalize_market_symbol("BTCEUR")

    assert normalize_market_symbol("BTC/EUR") == "BTC/EUR"
