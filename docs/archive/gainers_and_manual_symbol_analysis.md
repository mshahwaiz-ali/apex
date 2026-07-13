# Gainer Continuation and Manual Symbol Analysis

This document extends `docs/plan_2.md` with two required product capabilities.

## 1. Overextended Gainer Continuation Analysis

Apex must not reject every strong gainer merely because conventional indicators such as RSI are elevated.

RSI overbought is not, by itself, a short signal or a reason to reject a long setup. In strong momentum regimes, RSI can remain elevated while price continues trending.

Apex must classify strong gainers into distinct states:

- healthy momentum continuation
- controlled pullback continuation
- breakout expansion
- late-stage exhaustion
- blow-off or liquidation-risk move
- failed continuation reversal

The gainer-continuation model should evaluate:

- acceleration versus sustainable trend persistence
- relative volume and volume persistence
- candle body quality versus wick expansion
- distance from EMA 20, EMA 50, VWAP, and recent structure
- pullback depth and recovery quality
- available target space above current price
- nearest opposing liquidity or higher-timeframe resistance
- funding, open interest, and liquidation data when later available
- whether RSI is rising, flattening, or diverging rather than using only its absolute value
- breakout acceptance versus immediate rejection
- chase distance and stop expansion

### Required behavior

A strong gainer may still produce a `LONG` when:

- market structure remains intact
- momentum is supported by participation
- price is not excessively detached from logical support
- a controlled stop can be placed
- realistic target space remains
- liquidation and chase risk stay within configured limits

The setup must be downgraded or rejected when:

- the move is parabolic without support
- volume shows exhaustion or distribution
- repeated upper wicks show rejection
- price is too far from invalidation
- nearest target space is already consumed
- risk-to-reward deteriorates below the configured minimum

The system should introduce a dedicated strategy or strategy variant such as:

```text
momentum_gainer_continuation
```

This strategy must be tested separately from normal breakout and pullback strategies.

## 2. Manual Analysis of Any User-Selected Coin

Apex must allow the user to request analysis for any provider-supported symbol, even when that symbol is not present in the configured scanner universe.

Example commands:

```bash
apex analyze BTC/USDT
apex analyze WIF/USDT
apex analyze 1000PEPE/USDT
```

The scanner symbol list remains a curated universe for automated scanning. It must not restrict manual single-symbol analysis.

### Symbol handling requirements

Manual symbol input should:

- trim surrounding whitespace
- normalize case
- accept common compact forms such as `BTCUSDT` when unambiguous
- preserve exchange-specific prefixes such as `1000PEPE`
- validate base and quote assets
- reject malformed symbols clearly
- ask the configured provider whether the market is supported
- return an explicit unsupported-symbol error instead of silently changing the symbol

### Manual-symbol eligibility

The user may analyze a low-liquidity or unusual coin, but Apex must report eligibility warnings such as:

- insufficient candle history
- excessive spread
- weak volume
- stale market data
- abnormal volatility
- unsupported timeframe

Manual analysis should still use the complete deterministic pipeline:

```text
provider validation
-> multi-timeframe data
-> features
-> structure and liquidity
-> strategy candidates
-> scoring
-> risk assessment
-> LONG, SHORT, or NO_TRADE
```

## 3. Validation Requirements

Add fixture and historical tests for:

- strong gainer that continues despite high RSI
- high-RSI gainer entering exhaustion
- controlled pullback after a rapid gain
- breakout with no remaining target space
- manual symbol normalization
- compact symbol input
- invalid symbol syntax
- provider-supported symbol outside scanner configuration
- unsupported manual symbol

These capabilities must be included before Apex is considered feature-complete for discretionary user-selected analysis.
