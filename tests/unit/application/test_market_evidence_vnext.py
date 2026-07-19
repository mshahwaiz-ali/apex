from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.application.market_evidence import build_market_evidence_bundle
from apex.domain.futures_evidence import (
    FundingRateSnapshot,
    OpenInterestSnapshot,
    PremiumIndexSnapshot,
    TakerFlowSnapshot,
)

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


class EvidenceProvider:
    name = "fixture"

    def fetch_funding_rates(self, symbol: str, limit: int = 100) -> tuple[FundingRateSnapshot, ...]:
        return (FundingRateSnapshot(symbol, 0.0001, NOW - timedelta(hours=1), self.name),)

    def fetch_open_interest_history(
        self, symbol: str, period: str = "5m", limit: int = 100
    ) -> tuple[OpenInterestSnapshot, ...]:
        return (
            OpenInterestSnapshot(
                symbol, period, 100, 10_000, NOW - timedelta(minutes=5), self.name
            ),
            OpenInterestSnapshot(symbol, period, 102, 10_200, NOW, self.name),
        )

    def fetch_taker_flow_history(
        self, symbol: str, period: str = "5m", limit: int = 100
    ) -> tuple[TakerFlowSnapshot, ...]:
        return (TakerFlowSnapshot(symbol, period, 120, 100, 1.2, NOW, self.name),)

    def fetch_premium_index(self, symbol: str) -> PremiumIndexSnapshot:
        return PremiumIndexSnapshot(symbol, 101, 100, 0.0001, None, NOW, self.name)


def test_bundle_preserves_timestamped_evidence_and_basis() -> None:
    bundle = build_market_evidence_bundle(EvidenceProvider(), "BTCUSDT", as_of=NOW)

    assert bundle.available_inputs == ("funding", "open_interest", "taker_flow", "premium_index")
    assert bundle.premium_index is not None
    assert bundle.premium_index.basis_percentage == 1.0
    missing = dict(bundle.missing_reasons)
    assert not {"funding", "open_interest", "taker_flow", "premium_index"} & missing.keys()


def test_bundle_is_fail_soft_and_never_zero_fills_missing_inputs() -> None:
    class BrokenProvider:
        name = "broken"

    bundle = build_market_evidence_bundle(BrokenProvider(), "BTCUSDT", as_of=NOW)

    assert bundle.available_inputs == ()
    assert bundle.funding == ()
    assert dict(bundle.missing_reasons).keys() == {
        "exchange_filters",
        "funding",
        "open_interest",
        "order_book",
        "premium_index",
        "taker_flow",
        "ticker",
    }


def test_stale_series_is_explicitly_removed() -> None:
    provider = EvidenceProvider()
    bundle = build_market_evidence_bundle(provider, "BTCUSDT", as_of=NOW + timedelta(days=2))

    assert bundle.available_inputs == ()
    missing = dict(bundle.missing_reasons)
    assert all(
        missing[name] == "stale"
        for name in ("funding", "open_interest", "taker_flow", "premium_index")
    )
