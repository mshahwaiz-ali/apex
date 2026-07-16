# Architecture and Subsystems

## Layered architecture

Apex is organized so domain and strategy logic remain independent from providers, storage, CLI presentation, and future execution adapters.

```text
provider data
→ normalization and validation
→ reusable features
→ structure and liquidity analysis
→ strategy candidates
→ scoring and routing
→ risk and leverage approval
→ entry and lifecycle planning
→ reporting and persistence
```

## Core layers

### Domain

Pure models, enums, contracts, and invariant rules. Domain code must not depend on exchange APIs or CLI frameworks.

### Data

Provider adapters, historical and live candle retrieval, ticker and optional market-microstructure inputs, retries, caching, rate limiting, normalization, and validation.

### Features

Reusable calculations including EMA/SMA relationships, RSI, MACD, ATR, VWAP, Bollinger width, relative volume, momentum, volatility, candle statistics, and price-location measurements.

### Structure and liquidity

Swing detection, trend and range classification, break of structure, change of character, support/resistance, liquidity pools, sweeps, traps, failed breakouts, and extension analysis.

### Strategies and routing

Independent strategy families generate candidates. Regime and scanner routing decide which strategies are eligible or preferred without embedding position sizing inside strategy code.

Primary families include trend pullback, breakout continuation, breakout retest, liquidity-sweep reversal, range-edge reversal, momentum expansion, failed continuation, compression breakout, reclaim, retest, first-pullback continuation, and exhaustion reversal.

### Scoring

Transparent normalized component scores for structure, trend, entry quality, momentum, volume, liquidity, volatility, risk-to-reward, stop quality, extension, conflict, and data confidence.

### Risk and planning

Direction-aware entry classification, structural stops, targets, fees, slippage, position quantity, notional, isolated margin, leverage, wallet exposure, modeled maximum loss, liquidation estimate, and stop-to-liquidation buffer.

### Backtesting and paper trading

Chronological no-leakage replay, conservative intrabar handling, fees, slippage, partial exits, lifecycle rules, persistent trade state, portfolio exposure, and auditable result artifacts.

### Application

Small orchestration functions compose lower-level modules. The package facade must remain narrow to avoid import cycles; lower-level modules should import focused application modules directly.

### CLI and reporting

Typer commands provide human-readable and machine-readable output. CLI code coordinates inputs and presentation but does not own market logic.

## Timeframe roles

- `4h`: macro structure and extension
- `1h`: intermediate context and momentum regime
- `30m`: intraday structure
- `15m`: primary setup formation
- `5m`: entry structure and stop placement
- `3m`: microstructure refinement
- `1m`: precise timing only; never the entire thesis

## Storage

Use lightweight local storage appropriate to each artifact:

- JSON for portable reports and manifests
- SQLite for structured analysis and paper state
- JSONL for append-oriented datasets
- CSV or Parquet for historical candles and feature datasets

## Architectural constraints

- No hidden global state
- No provider-specific fields outside adapters
- No strategy logic in CLI modules
- No broad `Any` or type-ignore based contract repairs
- No execution authorization implied by analysis or readiness artifacts
- Configuration-driven thresholds and deterministic serialization
