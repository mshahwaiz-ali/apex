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

## S8 — Live spot eligibility and pre-filtering

Implemented on `main`; local validation remains required:

- provider-independent metadata construction from normalized ticker and closed `4h` candles;
- configurable quote-volume, spread, candle-count, ATR, downside-volatility, terminal-extension, exclusion, and optional market-age thresholds;
- exchange-boundary-aware candle-gap detection;
- explicit machine-readable eligibility reason codes;
- unavailable required measurements reject conservatively and market age is never fabricated;
- `eligible`, `watchlist`, and `all` scanner modes;
- deterministic `ranked`, `ineligible`, and `failures` payload sections;
- rejected symbols retain decision metadata and measurable inputs;
- provider failures remain distinct from eligibility rejection;
- no hidden score or futures-only semantics were introduced.
