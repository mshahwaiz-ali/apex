# Spot Workflow Progress

This document records implemented and locally reported behavior only. It does not claim profitability, funded-account eligibility, production readiness, or real-money safety.

## S5 — Provider-independent spot orchestration

Validated locally on 2026-07-15:

- canonical structure/regime input and six-strategy routing;
- bounded cash-spot planning only when a strategy is approved;
- deterministic sorted JSON and byte-identical optional output file;
- malformed structure and geometry rejection;
- strict mypy clean across 252 source files;
- 65 focused tests passed;
- installed `spot-plan`, `spot-analyze`, and `spot-orchestrate` commands verified.

## S6 — Live public-data spot orchestration

Validated locally on 2026-07-15:

- Binance public ticker and `4h` candle retrieval;
- provider-independent closed `12h` candle resampling from `4h` data;
- exchange close timestamps one millisecond before interval boundaries handled without accepting partial interior buckets;
- canonical spot structure, BTC-backed regime context, strategy routing, and bounded cash-spot result;
- strict mypy clean across 254 source files;
- 14 focused tests passed in the final boundary-validation batch;
- live JSON output, stdout/file byte equality, and recursive absence of futures-only fields verified.

## S7 — Live spot universe scanner

Validated locally on 2026-07-15:

- `apex spot-scan-live` accepts a comma-separated symbol universe;
- symbols are normalized and deduplicated deterministically;
- each symbol runs through the validated S6 pipeline;
- provider and validation failures are isolated per symbol;
- ranking uses plan availability, approved strategy state, evidence count, and symbol tie-breaking;
- output contains canonical analysis payloads plus explicit failures;
- no fabricated numeric scanner score is introduced;
- no leverage, margin, liquidation, borrowing, short-selling, order placement, or paper-position mutation is added.

## Live spot eligibility and pre-filtering

Validated locally on 2026-07-15:

- provider-independent metadata construction from normalized ticker and closed `4h` candles;
- configurable quote-volume, spread, candle-count, ATR, downside-volatility, terminal-extension, exclusion, and optional market-age thresholds;
- exchange-boundary-aware candle-gap detection;
- explicit machine-readable eligibility reason codes;
- unavailable required measurements reject conservatively and market age is never fabricated;
- `eligible`, `watchlist`, and `all` scanner modes;
- deterministic `ranked`, `ineligible`, and `failures` payload sections;
- rejected symbols retain decision metadata and measurable inputs;
- provider failures remain distinct from eligibility rejection;
- eligibility, reviewable, and hard-rejection ordering is deterministic;
- Ruff checks passed for the focused spot eligibility files;
- strict mypy clean across 257 source files;
- 26 focused tests passed;
- live Binance scans succeeded for BTCUSDT, ETHUSDT, and SOLUSDT in `eligible`, `watchlist`, and `all` modes;
- eligible-mode live output contained three ranked symbols, zero ineligible symbols, and zero failures;
- optional output remained byte-identical to stdout;
- no hidden score or futures-only semantics were introduced.

## S9 — Historical spot dataset, replay, and cash backtesting

Implemented on GitHub and awaiting local validation:

- explicit Binance Spot date-range dataset acquisition with forward pagination, closed-candle filtering, deterministic JSONL ordering, SHA-256 hashing, immutable manifests, atomic writes, and overwrite protection;
- leakage-safe replay using verified dataset hashes, common chronological decision timestamps, closed-candle visibility, `12h` resampling from visible `4h` candles, BTC-backed market regime context, canonical structure/strategy/planning reuse, deterministic replay records, and immutable replay manifests;
- chronological long-only cash-spot simulation consuming verified dataset and replay artifacts;
- earliest available execution timeframe selected independently per symbol from `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, and `4h`;
- no same-decision-candle lookahead and no exit processing on a candle that fills an entry leg;
- multiple limit-style entry legs, partial fills, maximum-chase rejection, entry expiry, and pre-fill invalidation;
- protective stops, partial targets, final targets, maximum holding exits, and end-of-dataset conversion to cash;
- conservative and optimistic same-candle stop/target policies;
- shared quote wallet with no leverage, borrowing, short-selling, liquidation-price semantics, or futures margin concepts;
- fees and slippage on both buys and sells, position-level cost basis, realized PnL, cash/equity curves, and exposure utilization;
- position-allocation, portfolio-exposure, quote-reserve, duplicate-position, and maximum-open-position controls;
- signal, eligibility, plan, fill, missed, expired, invalidated, trade, win-rate, expectancy, gross-profit, gross-loss, net-profit, profit-factor, fee, slippage, drawdown, ending-equity, holding-duration, and grouped performance outputs;
- source dataset, replay records, replay configuration, backtest configuration, and result hashes preserved in deterministic outputs and execution manifests;
- CLI commands: `spot-history-fetch`, `spot-history-replay`, and `spot-history-backtest`;
- focused execution-accounting, partial-fill, stop/target ambiguity, metrics, and exposure tests added.

S9 is not validated. Ruff, strict mypy, focused pytest, CLI help, historical fetch, replay, backtest, and manifest/hash smoke outputs must be supplied locally before validation is recorded.
