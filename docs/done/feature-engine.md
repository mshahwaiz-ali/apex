# Phase 2 Feature Engine

## Scope

The feature engine converts normalized `Candle` sequences into deterministic, provider-independent numerical features. It contains no strategy decisions, confidence scoring, trade direction, entry logic, or LLM dependency.

## Input policy

All calculations use `prepare_candles()` before numerical work.

The input sequence must:

- be non-empty
- contain one symbol, timeframe, and source
- be chronologically ordered
- contain no duplicate open timestamps
- place an active candle only in the final position
- contain the feature's minimum usable candle count

The default active-candle policy is `DROP_FINAL`. This makes repeated calculations stable while a live candle is changing. Features can explicitly use `REJECT` or `ALLOW_FINAL` when required by a future execution profile.

## Output policy

Features return typed `FeatureResult` objects with inspectable `FeatureSpec` metadata.

- series preserve deterministic candle ordering
- unavailable warm-up values are represented by `None`
- scalar results contain exactly one value
- NaN and infinite outputs are rejected
- no hidden state or lookahead is used

## Numerical decisions

### Moving averages

- SMA uses an aligned rolling arithmetic mean.
- EMA is seeded with the first complete SMA.
- EMA multiplier is `2 / (period + 1)`.

### Momentum

- RSI uses Wilder smoothing.
- RSI starts after `period` price changes, requiring `period + 1` closes.
- flat RSI windows resolve to `50`, all-gain windows to `100`, and all-loss windows to `0`.
- rate of change is percentage change from the close `period` observations earlier.
- MACD uses SMA-seeded fast, slow, and signal EMAs.

### Volatility

- true range uses the maximum of candle range and both previous-close gaps.
- ATR uses Wilder smoothing seeded by the first complete true-range average.
- ATR percentage divides ATR by close price and multiplies by `100`.
- Bollinger Bands use population standard deviation and configurable deviation count.
- Bollinger width is `(upper - lower) / middle * 100`.
- candle-range ratio compares current range with its rolling average.
- wick statistics are normalized by full candle range.

### Volume

- average volume is a rolling arithmetic mean.
- relative volume is current volume divided by rolling average volume.
- zero average volume produces relative volume `0` instead of an undefined value.
- volume spikes return deterministic numeric flags (`0.0` or `1.0`).
- doji volume is split equally between bullish and bearish pressure foundations.

### Price location

- recent range position is bounded to `0..1`.
- a zero-width recent range resolves to `0.5`.
- VWAP uses cumulative typical price `(high + low + close) / 3` weighted by volume.
- zero cumulative volume falls back to the current typical price.
- Bollinger position reports close location between lower and upper bands.

### Trend foundations

- fast/slow EMA spread is normalized by close price.
- EMA direction is `1`, `0`, or `-1`.
- EMA strength is the absolute normalized spread.
- EMA slope is percentage change per candle across a configurable lookback.
- price distance from EMA is a signed percentage.
- trend persistence averages close-above-EMA states over a rolling window and ranges from `-1` to `1`.

## Composition

`FeatureRegistry` is the application composition boundary. It registers named calculators, preserves registration order, rejects duplicate names, and can evaluate one group or all groups. The default registry provides the initial production feature set without introducing strategy logic.

## Implemented feature groups

- contracts and candle preparation
- numerical helpers
- SMA and EMA
- true range, ATR, and ATR percentage
- Bollinger Bands and width
- candle-range ratio and wick statistics
- RSI and RSI slope
- rate of change
- MACD, signal, and histogram
- average volume, relative volume, spike flags, and pressure foundations
- recent range position and distance from recent extremes
- VWAP and Bollinger position
- EMA relationship, EMA slope, price distance, persistence, and strength foundations
- typed feature registry

## Testing

The feature engine includes unit tests for contracts, validation, formulas, warm-up behavior, active-candle behavior, registry invariants, and invalid parameters. A JSON fixture anchors deterministic regression outputs for representative SMA, EMA, ATR, RSI, VWAP, and recent-range calculations.

## Verification

Phase 2 completion requires a green GitHub Actions quality run covering Ruff linting, Ruff formatting, strict mypy checks, and the complete pytest suite before Phase 3 begins.
