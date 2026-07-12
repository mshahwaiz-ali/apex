# Apex Trading Agent — Entry and Indicator Policy

## Status

This document is an authoritative amendment to `docs/plan.md`. Where entry-distance or indicator-use wording could be interpreted ambiguously, this policy takes precedence.

---

# 1. Entry Objective

Apex is not required to enter exactly at the current market price (`CMP`).

Its objective is to predict the best practical entry close enough to the current market that the system can capture a meaningful part of the expected move.

The entry engine must therefore optimize for:

* Directional alignment with the dominant setup thesis
* Structural validity
* Liquidity and invalidation quality
* Entry efficiency
* Realistic fill probability
* Risk-to-reward after fees and slippage
* Distance from the current market price
* Opportunity already lost before activation

A valid entry may be:

* At CMP
* Slightly above CMP for a justified momentum or breakout entry
* Slightly below CMP for a justified pullback, retest, or sweep-recovery entry
* A narrow scaled-entry zone around the optimal location

CMP is a reference point, not a mandatory execution price.

---

# 2. Near-CMP Requirement

Apex must not routinely return distant conditional entries that surrender most of the predicted move.

Example of unacceptable default behavior:

> Current price is 100. Enter long only after price reaches 104.

If the system expects the move from 100 toward 104 and beyond, it should attempt to identify a technically valid entry near 100 rather than waiting for the first four percent of the move to complete.

A distant confirmation entry may be returned only when evidence shows that entering earlier would be structurally invalid or unacceptably risky.

The output must explain why the distance is necessary.

---

# 3. Entry-Distance Controls

Entry distance must be volatility-aware rather than controlled by one universal percentage.

The engine should evaluate distance using measurements such as:

* Percentage distance from CMP
* ATR-normalized distance
* Distance relative to recent candle range
* Distance from the nearest structural level
* Distance from the expected invalidation point
* Remaining distance to the first realistic target
* Expected move already consumed

Each strategy and operating profile must define a maximum acceptable entry distance.

The engine should calculate and expose:

* Current market price
* Preferred entry price or narrow entry zone
* Percentage distance from CMP
* ATR-normalized distance from CMP
* Maximum acceptable chase price
* Maximum acceptable pullback distance
* Expected opportunity capture ratio
* Whether CMP is already inside the entry zone
* Whether the setup is actionable now, actionable nearby, or too distant

## 3.1 Opportunity capture ratio

The entry engine should estimate how much of the forecast move remains available from the proposed entry.

A concept such as the following should be used:

```text
remaining_expected_move / total_expected_move_from_current_price
```

A candidate that waits for a large part of the expected move to finish before entry should be downgraded or rejected unless the delayed confirmation materially improves survival probability.

---

# 4. Entry Selection Hierarchy

For each candidate, Apex should evaluate entry choices in this order:

1. Valid market-near entry
2. Nearby micro-pullback or retest
3. Nearby liquidity-sweep recovery or rejection entry
4. Nearby momentum continuation entry
5. Narrow scaled-entry zone
6. More distant confirmation only when earlier entries fail risk or structure rules
7. `NO_TRADE` when no nearby entry has acceptable expectancy

The system must not manufacture a low-quality CMP entry merely to stay close to price.

The required balance is:

> Enter as early and as near as reasonably possible, but never earlier than the setup evidence and invalidation structure justify.

---

# 5. Indicator and Feature Coverage

Apex will use a broad, modular technical feature library similar in coverage to professional charting platforms, while keeping all calculations deterministic, testable, and strategy-neutral.

The planned indicator families include, but are not limited to:

## 5.1 Trend

* EMA and SMA families
* Fast/slow moving-average relationships
* Moving-average slope
* Price distance from moving averages
* ADX and directional movement (`+DI` / `-DI`)
* Trend persistence
* Trend strength
* Supertrend-style volatility trend state, if validated

## 5.2 Momentum

* RSI
* RSI slope and regime
* Stochastic oscillator
* Stochastic RSI
* MACD and MACD histogram
* Rate of change
* Momentum acceleration and deceleration
* Divergence candidates
* Consecutive directional movement
* Williams %R or equivalent bounded momentum features, if validated

## 5.3 Volatility

* ATR and ATR percentage
* Bollinger Bands and band width
* Keltner-style channel features, if validated
* Range expansion and contraction
* Volatility percentile
* Wick abnormality
* Squeeze and release conditions

## 5.4 Volume and participation

* Average and relative volume
* Volume spikes
* Directional volume pressure
* Breakout participation
* Exhaustion volume
* VWAP and distance from VWAP
* Volume-price disagreement
* Optional order-book or trade-flow evidence when reliable data is available

## 5.5 Price location and structure

* Swing highs and lows
* Support and resistance
* Range position
* Liquidity pools and sweeps
* Break of structure and change of character
* Distance from VWAP, bands, averages, pivots, and range boundaries
* Extension and mean-reversion risk

---

# 6. Strategy Combinations

Indicators are not standalone trade signals and will not be combined through simple majority voting.

Apex will use strategy-specific evidence combinations.

Examples:

## 6.1 Trend pullback continuation

Possible evidence:

* Higher-timeframe bullish structure
* Price pulling back toward EMA, VWAP, support, or a flipped level
* RSI cooling without losing bullish regime
* Stochastic or Stochastic RSI resetting from overbought toward a continuation zone
* Momentum slope stabilizing or turning back with the trend
* Acceptable relative volume behavior
* Nearby structural invalidation

## 6.2 Liquidity-sweep reversal

Possible evidence:

* Equal highs/lows or clear liquidity zone
* Sweep and close recovery
* Momentum divergence or exhaustion
* Stochastic/RSI extreme leaving the extreme region
* Rejection candle structure
* Volume or participation evidence
* Favorable nearby invalidation

## 6.3 Breakout continuation

Possible evidence:

* Compression or range structure
* Close-confirmed breakout
* Relative-volume participation
* ADX or trend-strength expansion
* RSI/MACD momentum support
* No major nearby opposing liquidity
* Entry not excessively extended from the breakout boundary

## 6.4 Momentum expansion

Possible evidence:

* Multi-timeframe directional alignment
* Accelerating RSI, MACD histogram, or ROC
* Stochastic momentum aligned rather than already exhausted
* Expanding volume and volatility
* Clean structure and sufficient target space
* Strict late-entry and chase protection

Each strategy will define:

* Required evidence
* Optional supporting evidence
* Contradictions
* Invalidation rules
* Entry model
* Maximum acceptable CMP distance
* Scoring weights
* Backtest statistics

---

# 7. Indicator Governance

Adding many indicators does not automatically improve performance.

Every indicator or derived feature must:

* Have a clear purpose
* Be reusable and independent from strategy code
* Define required history and missing-data behavior
* Avoid future-data leakage
* Include unit tests
* Be evaluated for redundancy
* Be retained only when backtesting or forward testing shows measurable value

Highly correlated indicators must not be treated as independent confirmation.

For example, RSI, Stochastic RSI, and Williams %R may describe overlapping momentum information. The scoring system should group correlated evidence so one market condition is not counted multiple times merely because several formulas detect it.

---

# 8. Final Decision Rule

Apex should select the entry that maximizes expected trade quality under the following constraints:

```text
near enough to capture the opportunity
+ aligned with trend or validated reversal structure
+ supported by strategy-specific technical evidence
+ protected by logical invalidation
+ sufficient remaining target space
+ acceptable fees, slippage, and leverage risk
```

The engine should prefer a strong nearby entry over a safer-looking but excessively late confirmation that gives away a large portion of the forecast move.

It should prefer `NO_TRADE` over either:

* A forced CMP entry with weak structure
* A distant entry that is no longer meaningfully actionable
