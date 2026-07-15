# N4.8 — Historical Futures Shared-Wallet Campaign Replay

## Implemented

- Added deterministic chronological shared-wallet replay in `src/apex/backtesting/shared_wallet_replay.py`.
- Added shared historical futures campaign orchestration in `src/apex/backtesting/historical_futures_shared_campaign.py`.
- Added atomic shared result and manifest persistence in `src/apex/backtesting/historical_futures_shared_io.py`.
- Updated `apex dataset historical-futures-backtest` to use account-level shared-wallet replay.
- Added public exports for the stable N4.8 contracts and functions through `apex.backtesting`.
- Added focused import coverage for the public API.
- Added persisted integration coverage using real serialized historical signal records, the canonical historical futures simulator, chronological same-symbol overlap rejection, shared-wallet equity, deterministic output identity, manifest-to-result hashing, and overwrite refusal.

## Shared-wallet behavior

The replay:

- sorts candidates by signal time, symbol, and candidate ID;
- settles due positions before later admission decisions;
- tracks one shared equity balance;
- reserves and releases required margin;
- enforces available margin and maximum wallet exposure;
- enforces maximum concurrent positions;
- rejects overlapping same-symbol positions;
- applies daily realized-loss and consecutive-loss lockouts;
- records realized PnL, fees, peak equity, maximum drawdown, rejection counts, and an equity curve.

Wallet-rejected candidates remain visible as observations but do not contribute trades, fees, PnL, split trade metrics, or wallet equity.

## Margin evidence

Required margin is read only from serialized historical signal `position_size` evidence using these supported aliases:

```text
required_margin
margin_required
margin
```

Apex does not estimate missing required margin from quantity, notional, leverage, wallet size, stop distance, or defaults. Missing or invalid margin is rejected explicitly with:

```text
historical_required_margin_missing
```

## Persistence and reproducibility

- Result and execution-manifest paths must be distinct.
- Existing outputs are not overwritten.
- JSON artifacts are written atomically through temporary files.
- The persisted result is reloaded and canonical-hash verified.
- The persisted execution manifest is reloaded and checked against the result hash.
- Wallet configuration is hashed into the execution manifest.
- Equivalent inputs and wallet configuration produce equivalent result payload identity when written to separate output paths.

## Research-only status

N4.8 does not establish:

- historical edge;
- profitability;
- funded-account eligibility;
- production readiness;
- exchange execution readiness;
- real-money safety.

## Validation status

Earlier focused validation reported by the operator passed with Ruff, strict mypy, and 26 tests for the initial N4.8 implementation.

The new public export test, persisted integration test, and documentation changes have not yet been locally validated. A consolidated local Ruff, strict mypy, and pytest batch is required before this continuation is considered validated.
