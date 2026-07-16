# Development Roadmap

This roadmap summarizes the staged delivery model for Apex. Detailed completion status belongs in `docs/progress/implementation_progress.md`.

## Foundation

### Phase 0 — Repository foundation

- Installable Python package
- Configuration and logging
- Core domain contracts
- Typer CLI skeleton
- Ruff, strict mypy, pytest, and CI

### Phase 1 — Market data

- Provider abstraction
- Multi-timeframe OHLCV and ticker retrieval
- Validation, normalization, caching, retries, and rate limits
- Closed-candle and active-candle handling

### Phase 2 — Feature engine

- Trend, momentum, volatility, volume, and price-location features
- Deterministic feature registry
- Defined missing-data and numerical-stability behavior

### Phase 3 — Structure and liquidity

- Swings and pivots
- Trend, range, BOS, and CHoCH
- Support, resistance, liquidity zones, sweeps, traps, and failed breakouts

## Decision system

### Phase 4 — Strategy candidates

- Independent long and short strategy families
- Evidence and contradiction capture
- Regime-aware and scanner-aware routing

### Phase 5 — Scoring and selection

- Transparent score components
- Candidate ranking and rejection
- Meaningful `NO_TRADE` reasoning

### Phase 6 — Risk and leverage

- Entry zones, structural stops, targets, and risk-to-reward
- Quantity, notional, margin, wallet exposure, fees, and slippage
- Manual and automatic isolated leverage
- Liquidation estimate and stop buffer

### Phase 7 — Live analysis and scanner

- Single-symbol analysis
- Normal, gainer, and combined scanner modes
- Entry-state classification and near-current actionability
- Text, JSON, and persistent analysis records

## Evidence and lifecycle

### Phase 8 — Historical backtesting

- Chronological replay without future leakage
- Fees, slippage, partial exits, lifecycle rules, and conservative intrabar handling
- Strategy, regime, symbol, score-band, and leverage-band metrics

### Phase 9 — Paper trading

- Persistent portfolio and position lifecycle
- Entry, invalidation, partial exits, stop, target, expiry, and cancellation
- Account-aware exposure and modeled performance

### Phase 10 — Calibration

- Train, validation, and out-of-sample splits
- Walk-forward evaluation
- One controlled parameter group per experiment
- Expectancy, profit factor, drawdown, liquidation rate, and stability as primary measures

## Controlled execution

### Phase 11 — Funded-account readiness

- Verified provider limits
- Explicit provider-policy binding
- Forward-validation evidence
- Standard risk mode and account-policy gates
- Daily lockout, total-buffer, checklist, and kill-switch verification
- Readiness artifacts remain non-authorizing

### Phase 12 — Testnet execution

- Isolated-margin enforcement
- Exchange precision and filter handling
- Reduce-only exits
- Duplicate-order protection
- Reconciliation, audit records, and kill switches

Real-money execution is outside the default operating mode and requires separate explicit authorization and completed safety gates.

## Delivery rules

- Keep changes modular and deterministic.
- Add regression tests for fixed defects.
- Preserve public CLI behavior during refactors.
- Do not optimize against the same data used for final evaluation.
- Do not advance to new features while the full repository quality gate is failing.
