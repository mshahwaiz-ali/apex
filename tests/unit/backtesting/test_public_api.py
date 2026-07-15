"""Public import coverage for stable backtesting contracts."""

from apex.backtesting import (
    SHARED_HISTORICAL_FUTURES_SCHEMA_VERSION,
    SharedHistoricalFuturesCampaignResult,
    SharedHistoricalFuturesExecutionManifest,
    SharedWalletConfig,
    SharedWalletReplayResult,
    WalletEquityPoint,
    WalletRejectionCode,
    WalletReplayCandidate,
    WalletReplayDecision,
    execute_shared_historical_futures_campaign,
    replay_shared_wallet,
    write_shared_historical_futures_campaign,
)


def test_shared_wallet_contracts_are_publicly_importable() -> None:
    """Keep the supported N4.8 import surface explicit and stable."""

    exported = (
        SHARED_HISTORICAL_FUTURES_SCHEMA_VERSION,
        SharedHistoricalFuturesCampaignResult,
        SharedHistoricalFuturesExecutionManifest,
        SharedWalletConfig,
        SharedWalletReplayResult,
        WalletEquityPoint,
        WalletRejectionCode,
        WalletReplayCandidate,
        WalletReplayDecision,
        execute_shared_historical_futures_campaign,
        replay_shared_wallet,
        write_shared_historical_futures_campaign,
    )

    assert SHARED_HISTORICAL_FUTURES_SCHEMA_VERSION == 1
    assert all(item is not None for item in exported)
