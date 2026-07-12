# Apex Trading Agent

## Finalized Project Plan

## 1. Project Overview

**Apex Trading Agent** is a separate Python-based crypto market analysis system designed to identify aggressive, high-risk, high-reward trading opportunities near the current market price.

The system will analyze live market data across multiple timeframes, detect market structure and liquidity behavior, calculate technical features, evaluate long and short scenarios, and return structured trading setups containing:

* Market direction
* Entry zone
* Stop-loss
* Take-profit targets
* Risk-to-reward ratio
* Suggested leverage range
* Setup confidence
* Invalidation conditions
* Supporting market evidence
* Warnings and trade-management guidance

Apex is not intended to behave like a conservative signal bot that repeatedly says “wait for confirmation.” Its purpose is to actively search for the best currently actionable setup while still accounting for:

* Volatility
* Liquidity sweeps
* False breakouts
* Market traps
* Trend exhaustion
* Leverage risk
* Liquidation proximity
* Poor liquidity
* Conflicting timeframe structure

The system must remain analytical and disciplined. Aggressive does not mean random, uncontrolled, or based on a single indicator.

---

# 2. Core Project Goal

The primary goal is to build a system that can answer:

> Given the current market conditions, what is the strongest actionable crypto setup available near the current price?

For every analyzed market, Apex should determine one of the following:

* `LONG`
* `SHORT`
* `NO_TRADE`

When a trade is available, the system should provide the best practical entry near the current price rather than requiring an unnecessarily distant confirmation.

The system should still return `NO_TRADE` when:

* Market data is invalid or incomplete
* Liquidity is too poor
* Price behavior is unusually chaotic
* Risk cannot be controlled
* No setup reaches the minimum quality threshold
* The required stop-loss would be unreasonable
* Timeframes strongly contradict each other
* The opportunity is already too extended

`NO_TRADE` must be a meaningful analytical result, not the system’s default behavior.

---

# 3. Project Philosophy

Apex will follow these principles.

## 3.1 Aggressive but structured

The system should search for early and near-market entries, but every trade must still have:

* A defined thesis
* A clear invalidation point
* A measurable risk
* A logical target
* A minimum quality score

## 3.2 Deterministic before intelligent

The first production version will use deterministic Python logic.

We will not depend on an LLM for core trade decisions.

The initial system should be:

* Reproducible
* Testable
* Explainable
* Fast
* Free to run
* Independent of paid AI APIs

An LLM may be added later as an optional interpretation or reporting layer. It will not control the core signal engine unless testing proves that it improves measurable performance.

## 3.3 Evidence over indicator voting

The system will not simply count bullish and bearish indicators.

A setup must be based on combined evidence such as:

* Market structure
* Trend condition
* Momentum
* Volatility
* Volume
* Liquidity behavior
* Price location
* Multi-timeframe alignment
* Risk-to-reward quality

## 3.4 No promise of impossible accuracy

The project aims to produce unusually strong and actionable setups, but it will not claim guaranteed profitability or impossible win rates.

Performance will be judged through:

* Backtesting
* Forward testing
* Paper trading
* Setup-specific statistics
* Drawdown analysis
* Expectancy
* Risk-adjusted performance

## 3.5 Build first, optimize second

The development process will be:

1. Build a complete working system
2. Test every module
3. Establish baseline performance
4. Identify weaknesses using evidence
5. Improve one subsystem at a time
6. Compare every change against the baseline

---

# 4. Initial Scope

The first major version will be an analysis and paper-trading system.

It will not initially place real trades.

The initial scope includes:

* Live public crypto market data
* Multi-symbol scanning
* Multi-timeframe candle collection
* Technical feature calculations
* Market structure analysis
* Liquidity and trap detection
* Long and short setup generation
* Setup scoring
* Risk and leverage analysis
* Structured CLI output
* Machine-readable JSON output
* Historical backtesting
* Forward paper testing
* Logging and diagnostics
* Automated tests

Real order execution will only be considered after the analysis engine passes defined validation gates.

---

# 5. Market Coverage

## 5.1 Initial market type

The first version will focus on liquid cryptocurrency markets.

The initial implementation should prioritize:

* High-volume pairs
* Tight spreads
* Reliable candle history
* Reliable public data
* Markets that support both long and short analysis

The exact exchange integration will be isolated behind an adapter so the system can later support multiple exchanges without rewriting the strategy engine.

## 5.2 Symbol selection

Apex should support two operating modes.

### Single-symbol mode

Analyze one requested symbol in depth.

Example:

```text
Analyze BTC/USDT
```

### Market scanner mode

Analyze a configurable list of liquid symbols and rank the best current opportunities.

The scanner should prioritize quality over quantity.

It should not generate a signal for every market.

## 5.3 Symbol eligibility filters

Before strategy analysis, each symbol should pass eligibility checks such as:

* Minimum trading volume
* Maximum acceptable spread
* Minimum candle availability
* Valid price and volume data
* Sufficient recent activity
* No obvious data gaps
* Acceptable volatility conditions

---

# 6. Timeframe Model

The primary analysis timeframes are:

* `1m`
* `3m`
* `5m`
* `15m`
* `30m`
* `1h`
* `4h`

Each timeframe has a different purpose.

## 6.1 Higher-timeframe context

### 4h

Used for:

* Major trend
* Large market structure
* Major support and resistance
* Macro directional bias
* Extended market detection

### 1h

Used for:

* Intermediate trend
* Important structure shifts
* Momentum regime
* Major liquidity zones
* Context for lower-timeframe setups

## 6.2 Setup timeframes

### 30m

Used for:

* Intraday structure
* Key levels
* Trend continuation or reversal context
* Volatility regime

### 15m

Used for:

* Primary setup formation
* Support and resistance zones
* Breakout and rejection patterns
* Momentum alignment

### 5m

Used for:

* Entry structure
* Local liquidity behavior
* Rejection or continuation confirmation
* Stop-loss positioning

## 6.3 Execution timeframes

### 3m

Used for:

* Entry refinement
* Microstructure
* Sweep detection
* Short-term momentum

### 1m

Used cautiously for:

* Precise entry timing
* Immediate liquidity events
* Very short-term momentum
* Avoiding poor entry fills

The 1-minute timeframe must never determine the entire trade thesis by itself.

---

# 7. System Architecture

Apex will use a modular architecture.

```text
apex/
├── README.md
├── plan.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── config/
│   ├── default.yaml
│   ├── symbols.yaml
│   ├── strategies.yaml
│   └── risk.yaml
├── src/
│   └── apex/
│       ├── __init__.py
│       ├── cli.py
│       ├── application/
│       ├── config/
│       ├── data/
│       ├── domain/
│       ├── features/
│       ├── structure/
│       ├── liquidity/
│       ├── strategies/
│       ├── scoring/
│       ├── risk/
│       ├── scanner/
│       ├── backtesting/
│       ├── paper_trading/
│       ├── reporting/
│       ├── storage/
│       └── monitoring/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── regression/
│   ├── backtesting/
│   └── fixtures/
├── scripts/
├── data/
│   ├── raw/
│   ├── processed/
│   ├── cache/
│   └── reports/
├── logs/
└── docs/
```

Runtime folders such as `data/`, `logs/`, and caches should remain excluded from Git except for placeholder files where needed.

---

# 8. Architectural Layers

## 8.1 Domain layer

The domain layer will contain pure business models and rules.

Core models may include:

* `Candle`
* `OrderBookSnapshot`
* `TickerSnapshot`
* `MarketSnapshot`
* `TimeframeAnalysis`
* `MarketStructure`
* `LiquidityEvent`
* `TradeCandidate`
* `TradeSetup`
* `RiskProfile`
* `BacktestTrade`
* `PaperTrade`
* `AnalysisResult`

The domain layer must not depend directly on external APIs.

## 8.2 Data layer

Responsible for:

* Exchange communication
* Historical candle retrieval
* Live candle updates
* Ticker data
* Optional order-book data
* Caching
* Validation
* Retry handling
* Rate-limit protection
* Data normalization

## 8.3 Feature layer

Responsible for calculating reusable market features.

Examples:

* Moving averages
* RSI
* MACD
* ATR
* Bollinger Bands
* Volume averages
* VWAP
* Rate of change
* Candle statistics
* Trend slope
* Volatility percentile
* Relative volume
* Distance from important levels

## 8.4 Market structure layer

Responsible for:

* Swing highs
* Swing lows
* Higher highs
* Higher lows
* Lower highs
* Lower lows
* Break of structure
* Change of character
* Trend regime
* Range detection
* Consolidation detection
* Support and resistance zones

## 8.5 Liquidity layer

Responsible for identifying:

* Equal highs
* Equal lows
* Recent swing liquidity
* Stop-hunt areas
* Liquidity sweeps
* Failed breakouts
* Long traps
* Short traps
* Wick rejection
* Volume-supported breakouts
* Volume-unsupported breakouts

## 8.6 Strategy layer

Responsible for generating candidate setups.

Strategies will remain separate from scoring and risk.

Each strategy should return:

* Direction
* Entry concept
* Invalidation concept
* Target concept
* Supporting evidence
* Contradictions
* Strategy-specific metadata

## 8.7 Scoring layer

Responsible for comparing candidates using a normalized scoring model.

## 8.8 Risk layer

Responsible for:

* Stop placement
* Position sizing
* Target calculation
* Risk-to-reward
* Leverage constraints
* Liquidation-distance checks
* Maximum allowed trade risk
* Trade rejection when risk is structurally poor

## 8.9 Application layer

Responsible for orchestrating the full workflow.

Example:

```text
collect data
→ validate data
→ calculate features
→ analyze structure
→ detect liquidity events
→ generate candidates
→ score candidates
→ apply risk rules
→ select best setup
→ format output
→ record result
```

---

# 9. Market Data System

## 9.1 Data-source requirements

The initial data source should provide free public access to:

* OHLCV candles
* Current ticker price
* Trading volume
* Historical candles
* Multiple timeframes

Optional later inputs include:

* Order-book depth
* Funding rate
* Open interest
* Liquidation data
* Trade flow
* Market-wide breadth

The data adapter must make it possible to replace or add providers later.

## 9.2 Data normalization

All external market data must be converted into internal models.

The rest of the system should not depend on provider-specific field names.

Each candle should include:

* Symbol
* Timeframe
* Open time
* Close time
* Open
* High
* Low
* Close
* Volume
* Closed-candle status
* Source

## 9.3 Closed and active candles

Apex must distinguish between:

* Fully closed candles
* The currently forming candle

Closed candles should be used for stable calculations.

The active candle may be used for live entry analysis, but its provisional nature must be tracked.

## 9.4 Data validation

Data should be rejected or flagged when:

* Candles are missing
* Timestamps are duplicated
* Candle ordering is wrong
* High is below open or close
* Low is above open or close
* Volume is negative
* Timeframe intervals are inconsistent
* Data is stale
* The current price is invalid

## 9.5 Caching

Historical candles should be cached locally to:

* Reduce API requests
* Improve speed
* Support reproducible tests
* Allow offline development
* Reduce rate-limit risk

Cache behavior must be configurable.

---

# 10. Feature and Indicator Engine

Indicators should be implemented as reusable feature calculators.

The initial feature set should include:

## 10.1 Trend features

* Exponential moving averages
* Simple moving averages
* Fast and slow EMA relationships
* EMA slope
* Price distance from EMA
* Trend persistence
* Trend strength

## 10.2 Momentum features

* RSI
* RSI slope
* MACD
* MACD histogram
* Rate of change
* Consecutive bullish or bearish movement
* Momentum divergence candidates

## 10.3 Volatility features

* ATR
* ATR percentage
* Bollinger Band width
* Candle-range expansion
* Candle-range contraction
* Current volatility percentile
* Abnormal wick size
* Volatility regime

## 10.4 Volume features

* Average volume
* Relative volume
* Volume spike
* Bullish and bearish volume pressure
* Breakout volume confirmation
* Exhaustion volume

## 10.5 Price-location features

* Distance from recent swing high
* Distance from recent swing low
* Distance from support
* Distance from resistance
* Distance from VWAP
* Position within recent range
* Position within Bollinger Bands
* Extension from moving averages

Every feature must define:

* Required input length
* Output type
* Missing-data behavior
* Numerical stability behavior
* Unit tests

---

# 11. Market Structure Engine

The structure engine is one of the most important parts of Apex.

It must convert raw candle movement into a structured market interpretation.

## 11.1 Swing detection

The system should identify local:

* Swing highs
* Swing lows
* Confirmed pivots
* Developing pivots

Swing sensitivity should be configurable by timeframe and volatility.

## 11.2 Trend classification

Each timeframe should be classified as:

* Strong bullish trend
* Bullish trend
* Weak bullish trend
* Range
* Weak bearish trend
* Bearish trend
* Strong bearish trend
* Transition or uncertain

## 11.3 Break of structure

A bullish break of structure may occur when price breaks a meaningful prior high with sufficient quality.

A bearish break of structure may occur when price breaks a meaningful prior low.

Break quality should consider:

* Closing price
* Wick versus body break
* Relative volume
* Break distance
* Immediate rejection
* Higher-timeframe context

## 11.4 Change of character

The system should detect potential early reversals when an established directional structure breaks in the opposite direction.

This should not automatically become a reversal trade. It should increase reversal probability when combined with other evidence.

## 11.5 Range detection

Apex must identify ranges to avoid applying trend logic incorrectly.

Range analysis should include:

* Range high
* Range low
* Midpoint
* Range width
* Number of boundary tests
* False breaks
* Current location within range

---

# 12. Liquidity and Trap Detection

## 12.1 Liquidity zones

Potential liquidity areas include:

* Equal highs
* Equal lows
* Recent obvious swing highs
* Recent obvious swing lows
* Range boundaries
* Session highs and lows
* Clustered rejection points

## 12.2 Liquidity sweep

A sweep may be detected when:

1. Price trades beyond a known liquidity level
2. The move fails to sustain
3. Price closes back inside the prior structure
4. Rejection or reversal evidence appears

Sweep strength should consider:

* Wick size
* Close position
* Relative volume
* Follow-through
* Higher-timeframe location
* Distance from the swept level

## 12.3 False breakout

A false breakout may occur when:

* Price breaks a structure level
* Volume does not support the move
* Price quickly closes back within the range
* Opposite momentum appears
* The breakout occurs into higher-timeframe resistance or support

## 12.4 Trap classification

The system should identify:

* Bull traps
* Bear traps
* Long liquidation traps
* Short squeeze conditions
* Breakout-chasing risk
* Late-entry risk

---

# 13. Initial Strategy Families

Each strategy will be implemented independently and tested independently.

## 13.1 Trend pullback continuation

Purpose:

Enter an established trend after a controlled pullback.

Long conditions may include:

* Higher-timeframe bullish structure
* Price pulling into a valid support area
* Momentum cooling without collapsing
* No major bearish structural break
* Entry-timeframe rejection or renewed momentum

Short conditions are the inverse.

## 13.2 Breakout continuation

Purpose:

Enter a genuine breakout with sufficient momentum and volume.

Conditions may include:

* Defined consolidation or range
* Structural breakout
* Volume expansion
* Acceptable distance from breakout level
* No immediate rejection
* Valid risk-to-reward

Apex must reject late breakouts when price is already excessively extended.

## 13.3 Breakout retest

Purpose:

Enter after price breaks a meaningful level and successfully retests it.

This strategy may offer:

* Better stop placement
* Improved risk-to-reward
* Reduced false-breakout risk

## 13.4 Liquidity sweep reversal

Purpose:

Enter after price sweeps a known liquidity area and rejects it.

Conditions may include:

* Clear liquidity level
* Sweep beyond the level
* Strong rejection
* Structure recovery
* Supporting momentum or volume
* Sufficient target space

## 13.5 Range-edge reversal

Purpose:

Trade from a validated range boundary toward the range interior or opposite boundary.

The system should avoid entries near the range midpoint.

## 13.6 Momentum expansion

Purpose:

Capture a rapid directional move during expanding momentum and volume.

This is an aggressive strategy and requires strict controls against chasing an overextended candle.

## 13.7 Failed continuation reversal

Purpose:

Trade against a trend when a continuation attempt fails at an important level and structure begins shifting.

This strategy should require stronger evidence than a normal continuation setup.

## 13.8 Compression breakout

Purpose:

Detect low-volatility compression followed by probable expansion.

Conditions may include:

* Falling ATR
* Narrowing bands
* Reduced candle range
* Defined compression structure
* Directional trigger
* Volume expansion

---

# 14. Multi-Timeframe Analysis

Each timeframe should return an independent analysis.

A combined market view will then be built from those analyses.

## 14.1 Timeframe analysis output

Each timeframe should report:

* Trend
* Momentum
* Volatility
* Volume condition
* Structure
* Support levels
* Resistance levels
* Liquidity levels
* Breakout state
* Extension state
* Data confidence

## 14.2 Context hierarchy

Higher timeframes provide context.

Lower timeframes provide execution.

The system should not require perfect alignment across all timeframes.

Instead, it should distinguish between:

* Full alignment
* Partial alignment
* Lower-timeframe countertrend setup
* Higher-timeframe reversal setup
* Severe contradiction

## 14.3 Weighted alignment

Suggested initial weighting:

* `4h`: macro context
* `1h`: strong contextual weight
* `30m`: setup context
* `15m`: primary setup weight
* `5m`: entry weight
* `3m`: refinement weight
* `1m`: timing weight

The final weights must remain configurable and will later be optimized through testing.

---

# 15. Candidate Generation

Each strategy can generate zero or more `TradeCandidate` objects.

A candidate should contain:

```text
symbol
direction
strategy
current_price
entry_zone
proposed_stop
proposed_targets
supporting_factors
contradicting_factors
timeframe_context
raw_score_components
risk_metadata
```

Candidates should not yet be considered valid trades.

They must pass:

1. Data checks
2. Structural checks
3. Scoring
4. Risk validation
5. Duplication handling
6. Final ranking

---

# 16. Setup Scoring Model

The scoring engine should produce transparent component scores.

A possible normalized score range is:

```text
0–100
```

Initial components may include:

| Component              | Purpose                                      |
| ---------------------- | -------------------------------------------- |
| Trend alignment        | Measures directional agreement               |
| Structure quality      | Measures structural validity                 |
| Entry quality          | Measures entry location                      |
| Momentum               | Measures directional strength                |
| Volume                 | Measures participation                       |
| Liquidity evidence     | Measures sweep or trap quality               |
| Volatility suitability | Checks whether volatility supports the setup |
| Risk-to-reward         | Measures target quality                      |
| Stop quality           | Measures logical invalidation                |
| Extension penalty      | Penalizes chasing                            |
| Conflict penalty       | Penalizes contradictory evidence             |
| Data confidence        | Penalizes incomplete or unreliable data      |

## 16.1 Score bands

Initial interpretation:

* `85–100`: exceptional setup
* `75–84`: strong setup
* `65–74`: valid but aggressive setup
* `55–64`: weak or experimental setup
* `<55`: reject

These thresholds are starting values only.

They must be calibrated using historical and forward-test results.

## 16.2 Explainable scores

The system must return a score breakdown.

Example:

```json
{
  "total_score": 81.5,
  "components": {
    "trend_alignment": 14,
    "structure_quality": 16,
    "entry_quality": 13,
    "momentum": 10,
    "volume": 8,
    "liquidity": 12,
    "risk_reward": 11,
    "extension_penalty": -3
  }
}
```

---

# 17. Entry Engine

The entry engine should calculate a practical zone rather than only a single exact number.

## 17.1 Entry types

Supported entry types may include:

* Market-near entry
* Pullback entry
* Retest entry
* Breakout entry
* Rejection entry
* Scaled entry zone

## 17.2 Near-current-price requirement

Apex should prefer entries close to the current market price when the setup remains valid.

It should avoid returning an entry that is so distant that the opportunity is no longer actionable.

The output should state:

* Current price
* Entry lower bound
* Entry upper bound
* Maximum acceptable chase price
* Whether the current price is already inside the entry zone

## 17.3 Chase protection

The system should reject or downgrade a setup when:

* Price has moved too far from the logical entry
* Stop distance has expanded significantly
* Risk-to-reward has deteriorated
* The breakout candle is abnormally extended
* The nearest target is now too close

---

# 18. Stop-Loss Engine

Stops must be structural rather than arbitrary.

Possible stop references include:

* Swing low or high
* Sweep extreme
* Range boundary
* Retest failure point
* ATR-adjusted invalidation
* Structure-break invalidation

The system should account for:

* Normal market noise
* Spread
* Volatility
* Wick behavior
* Timeframe
* Entry type

The stop engine should reject setups where:

* The stop is unrealistically tight
* The stop is excessively wide
* The stop is not linked to the thesis
* Normal volatility would invalidate the trade
* The required leverage would create unacceptable liquidation risk

---

# 19. Target Engine

The system should support multiple targets.

Example:

* `TP1`: conservative
* `TP2`: primary
* `TP3`: extended

Target sources may include:

* Recent swing level
* Opposing liquidity
* Range boundary
* Higher-timeframe support or resistance
* ATR projection
* Measured move
* Fixed risk multiple

Each target should include:

* Target price
* Estimated reward
* Risk-to-reward ratio
* Target rationale
* Optional partial-close percentage

The system should not force unrealistic targets simply to create an attractive risk-to-reward ratio.

---

# 20. Risk and Position Sizing

## 20.1 Account risk

Risk should be configurable as a percentage of account equity.

The system should calculate:

```text
risk amount = account equity × risk percentage
```

```text
position size = risk amount ÷ stop distance
```

## 20.2 Aggressive risk profiles

Apex may support configurable profiles such as:

* `controlled`
* `aggressive`
* `extreme`

These profiles should modify:

* Maximum account risk
* Minimum setup score
* Maximum leverage
* Maximum stop distance
* Allowed strategy types
* Concurrent exposure

The default development and testing profile should remain controlled enough to evaluate the strategy objectively.

## 20.3 Exposure controls

The risk engine should consider:

* Total open risk
* Correlated positions
* Same-direction market exposure
* Multiple positions on highly correlated assets
* Maximum simultaneous trades
* Daily loss limits
* Consecutive loss limits

---

# 21. Leverage Engine

Leverage must be treated as a risk parameter, not a profit multiplier.

Suggested leverage should consider:

* Stop-loss distance
* Volatility
* Market liquidity
* Setup score
* Entry precision
* Estimated liquidation distance
* Account risk limits

The system should return a range rather than blindly recommending maximum leverage.

Example:

```text
Suggested leverage: 3x–5x
Maximum modeled leverage: 7x
```

The recommended leverage must keep liquidation meaningfully beyond the stop-loss.

A trade should be rejected when the liquidation price would be too close to the invalidation level.

---

# 22. Trade Output Format

A valid setup should include:

```json
{
  "symbol": "BTC/USDT",
  "decision": "LONG",
  "strategy": "liquidity_sweep_reversal",
  "current_price": 0,
  "entry_zone": {
    "low": 0,
    "high": 0
  },
  "stop_loss": 0,
  "take_profits": [
    {
      "label": "TP1",
      "price": 0,
      "risk_reward": 0
    }
  ],
  "suggested_leverage": {
    "minimum": 0,
    "maximum": 0
  },
  "confidence_score": 0,
  "risk_level": "high",
  "timeframe_bias": {},
  "supporting_evidence": [],
  "contradictions": [],
  "invalidation": [],
  "warnings": [],
  "generated_at": ""
}
```

A `NO_TRADE` result should explain why:

```json
{
  "symbol": "BTC/USDT",
  "decision": "NO_TRADE",
  "reasons": [
    "Price is excessively extended",
    "Risk-to-reward is below the configured minimum"
  ],
  "best_candidate_score": 48.2,
  "generated_at": ""
}
```

---

# 23. Opportunity Scanner

The scanner will:

1. Load the configured symbol universe
2. Apply liquidity and data eligibility filters
3. Analyze symbols concurrently within safe limits
4. Generate long and short candidates
5. Apply scoring and risk validation
6. Rank valid setups
7. Return the strongest opportunities

Scanner output should include:

* Best overall setup
* Top long setups
* Top short setups
* Rejected high-potential setups
* Market regime summary
* Analysis timestamp

The scanner should avoid overloading the provider and must implement:

* Rate limiting
* Retry control
* Concurrency limits
* Request caching
* Failure isolation

One failed symbol should not stop the entire scan.

---

# 24. Market-Regime Detection

Before selecting strategies, Apex should classify the broader environment.

Possible regimes:

* Strong trend
* Weak trend
* Range
* Breakout expansion
* Volatility compression
* High-volatility chaos
* Reversal transition
* Low-liquidity condition

Strategy eligibility should depend on the regime.

Examples:

* Trend pullbacks perform better in trends
* Range reversals perform better in stable ranges
* Compression breakouts require volatility contraction
* Momentum entries should be restricted during chaotic conditions

---

# 25. Backtesting System

The backtester must simulate strategy behavior without future-data leakage.

## 25.1 Backtesting requirements

The system should support:

* Historical candle loading
* Chronological analysis
* Signal generation using only available data
* Entry simulation
* Stop and target simulation
* Trading fees
* Slippage assumptions
* Partial profit-taking
* Trade expiration
* Maximum holding period
* Strategy-specific results

## 25.2 Intrabar ambiguity

When both the stop and target appear inside the same candle, the engine must not automatically assume the profitable outcome.

The system should use a configurable conservative execution rule.

## 25.3 Metrics

Backtesting reports should include:

* Number of trades
* Win rate
* Loss rate
* Breakeven rate
* Gross profit
* Gross loss
* Net profit
* Profit factor
* Average win
* Average loss
* Average risk-to-reward
* Expectancy per trade
* Maximum drawdown
* Consecutive wins
* Consecutive losses
* Sharpe-like risk-adjusted metric
* Performance by symbol
* Performance by timeframe
* Performance by strategy
* Performance by market regime
* Performance by score band
* Performance by leverage band

## 25.4 Walk-forward validation

Apex should avoid optimizing and testing on the same data.

Historical data should be separated into:

* Training or development period
* Validation period
* Out-of-sample test period

Later versions should support walk-forward testing.

---

# 26. Paper-Trading System

After backtesting, Apex will run in forward paper-trading mode.

The paper trader should:

* Record generated setups
* Simulate entries
* Track open positions
* Update stop and target status
* Record fees and slippage
* Close expired trades
* Calculate live paper performance
* Store the original analysis for later review

This is essential because historical backtesting cannot perfectly reproduce live conditions.

---

# 27. Signal Lifecycle

Every generated setup should have a lifecycle.

Possible states:

* `generated`
* `waiting_for_entry`
* `entered`
* `partially_closed`
* `stopped`
* `target_hit`
* `expired`
* `cancelled`
* `invalidated`

A setup should expire when:

* The entry zone is not reached within its allowed lifetime
* The market structure changes
* The setup score falls below the threshold
* Price reaches the target before entry
* Price violates the stop before entry
* The market becomes stale or unavailable

---

# 28. Storage Strategy

The initial version should remain simple and local.

Recommended initial storage:

* JSON for exported analysis
* CSV or Parquet for candle and test datasets
* SQLite for structured paper-trading and analysis history

A heavy database framework is not required for the first version.

Frappe is not necessary for the analysis engine.

It may only be considered later if Apex requires:

* A multi-user dashboard
* Administrative workflows
* Role permissions
* Web-based reports
* Hosted operational management

The trading logic must remain independent of any future UI or framework.

---

# 29. Configuration System

Behavior should be controlled through configuration rather than hardcoded constants.

Configuration categories:

## General

* Environment
* Logging level
* Data directories
* Cache settings
* Default symbols
* Default timeframes

## Data

* Provider
* Request timeout
* Retry count
* Rate limit
* Candle history length
* Cache lifetime

## Strategy

* Enabled strategies
* Strategy thresholds
* Timeframe weights
* Indicator periods
* Structure sensitivity
* Liquidity sensitivity

## Scoring

* Component weights
* Minimum score
* Penalties
* Confidence mapping

## Risk

* Account size
* Risk per trade
* Maximum daily risk
* Minimum risk-to-reward
* Maximum leverage
* Maximum concurrent trades

## Backtesting

* Fee rate
* Slippage
* Starting capital
* Date range
* Symbols
* Execution assumptions

Sensitive values must use environment variables and must never be committed.

---

# 30. Logging and Observability

Apex should produce structured logs.

Logging categories:

* Data requests
* Data validation failures
* Feature calculations
* Strategy candidates
* Rejected candidates
* Score breakdowns
* Risk rejections
* Backtest execution
* Paper-trade lifecycle
* Unexpected exceptions

Each analysis should have an analysis ID for traceability.

Logs should answer:

* What data was used?
* Which strategies ran?
* Which candidates were created?
* Why was a candidate rejected?
* Why was the final setup selected?
* Which configuration was active?

---

# 31. Error Handling

The system should fail safely.

Expected error categories:

* Network failure
* Provider rate limit
* Invalid response
* Missing candles
* Stale data
* Unsupported symbol
* Numerical calculation failure
* Configuration error
* Storage failure
* Strategy failure

Rules:

* One failed timeframe should reduce confidence or reject the symbol
* One failed symbol should not stop the market scanner
* One failed strategy should not stop unrelated strategies
* Critical data corruption should produce `NO_TRADE`
* Exceptions must include enough context for debugging

---

# 32. Testing Strategy

Testing is a core project requirement.

## 32.1 Unit tests

Required for:

* Candle validation
* Indicator calculations
* Swing detection
* Structure detection
* Liquidity detection
* Strategy conditions
* Score calculations
* Stop calculations
* Target calculations
* Position sizing
* Leverage rules
* Configuration loading

## 32.2 Integration tests

Required for:

* Provider adapter
* Candle retrieval
* Cache behavior
* Multi-timeframe pipeline
* Full symbol analysis
* Scanner flow
* Storage
* CLI commands

## 32.3 Regression tests

When a bug is fixed, a test must be added to prevent recurrence.

## 32.4 Fixture-based tests

Representative market scenarios should be stored as fixtures:

* Uptrend pullback
* Downtrend pullback
* Bull trap
* Bear trap
* Liquidity sweep
* Range breakout
* False breakout
* Volatility compression
* Extreme volatility
* Missing data
* Flat market

## 32.5 Property and invariant tests

Important invariants include:

* Candle high must not be below candle low
* Long stop must be below the entry
* Short stop must be above the entry
* Position size must not exceed configured risk
* Suggested leverage must not violate liquidation rules
* Targets must be directionally valid
* No result may contain NaN or infinite values

---

# 33. Code Quality Standards

The project should use:

* Modern Python
* Type hints
* Clear module boundaries
* Small testable functions
* Dataclasses or validated models
* Consistent formatting
* Static analysis
* Automated tests
* Clear docstrings for public APIs
* No hidden global state
* Dependency injection where useful

The project should avoid:

* Large monolithic files
* Strategy logic inside CLI code
* Provider-specific fields throughout the system
* Hardcoded secrets
* Silent exception handling
* Unexplained score constants
* Uncontrolled concurrency
* Premature framework complexity

---

# 34. Command-Line Interface

The initial user interface will be a CLI.

Potential commands:

```bash
apex analyze BTC/USDT
```

```bash
apex scan
```

```bash
apex backtest --strategy trend_pullback
```

```bash
apex paper start
```

```bash
apex report latest
```

```bash
apex validate-config
```

CLI output should support:

* Human-readable text
* JSON
* Optional file export

---

# 35. Development Phases

## Phase 0 — Repository foundation

Deliverables:

* Python project configuration
* Source layout
* Test layout
* Configuration loader
* Logging setup
* CLI skeleton
* Basic domain models
* Code-quality tooling
* Initial CI test workflow

Completion criteria:

* Project installs successfully
* CLI launches
* Tests run
* Configuration validates
* Logging works

## Phase 1 — Market data foundation

Deliverables:

* Provider interface
* Initial public-data provider adapter
* OHLCV retrieval
* Ticker retrieval
* Data normalization
* Validation
* Caching
* Retry and rate-limit handling

Completion criteria:

* Real candles can be fetched
* Multiple timeframes work
* Invalid data is rejected
* Cached and live results are consistent

## Phase 2 — Feature engine

Deliverables:

* Trend indicators
* Momentum indicators
* Volatility indicators
* Volume indicators
* Price-location features
* Feature registry

Completion criteria:

* Features are deterministic
* Numerical outputs are tested
* Missing-data behavior is defined

## Phase 3 — Structure and liquidity

Deliverables:

* Swing detection
* Trend classification
* Break of structure
* Change of character
* Range detection
* Support and resistance
* Liquidity zones
* Sweep and trap detection

Completion criteria:

* Fixture scenarios produce expected structure
* Important events include explanations

## Phase 4 — Strategy engine

Deliverables:

* Candidate interface
* Initial strategy families
* Long and short generation
* Candidate evidence
* Contradiction tracking

Completion criteria:

* Strategies generate candidates independently
* Strategies do not directly control position sizing
* Every candidate explains its thesis

## Phase 5 — Scoring and selection

Deliverables:

* Score components
* Configurable weights
* Penalties
* Candidate comparison
* Final setup selection
* `NO_TRADE` reasoning

Completion criteria:

* Scores are reproducible
* Score breakdowns are visible
* Weak candidates are consistently rejected

## Phase 6 — Risk engine

Deliverables:

* Entry zones
* Stops
* Targets
* Risk-to-reward
* Position size
* Leverage range
* Liquidation checks
* Exposure limits

Completion criteria:

* Every valid trade has controlled risk
* Invalid risk structures are rejected
* Position sizing passes invariant tests

## Phase 7 — CLI analysis and scanner

Deliverables:

* Single-symbol command
* Multi-symbol scanner
* Ranking
* Text output
* JSON output
* Report export

Completion criteria:

* A complete analysis can run from one command
* Scanner failures are isolated
* Results are understandable without reading logs

## Phase 8 — Backtesting

Deliverables:

* Historical replay
* Trade simulation
* Fees
* Slippage
* Partial targets
* Metrics
* Strategy reports
* Out-of-sample testing

Completion criteria:

* No lookahead bias
* Results are reproducible
* Performance is broken down by strategy and regime

## Phase 9 — Paper trading

Deliverables:

* Setup tracking
* Entry simulation
* Position lifecycle
* Live metrics
* Persistent history
* Daily reports

Completion criteria:

* The system can run continuously without real orders
* Every setup can be audited afterward

## Phase 10 — Optimization

Deliverables:

* Threshold calibration
* Strategy-specific score tuning
* Regime-specific tuning
* Symbol filtering improvements
* False-positive reduction
* Entry and stop improvements

Rules:

* One major variable group should be changed at a time
* Every change must be measured against the baseline
* Improvements must work on out-of-sample data
* Changes that only improve win rate while damaging expectancy should be rejected

## Phase 11 — Advanced intelligence

Potential additions:

* Funding-rate analysis
* Open-interest analysis
* Order-book imbalance
* Liquidation maps
* Trade-flow analysis
* Correlation analysis
* Market-wide risk state
* Optional machine-learning ranking
* Optional LLM-generated natural-language explanations

These additions will only be introduced when the deterministic baseline is stable.

## Phase 12 — Optional execution

Real trade execution may be considered only after all safety gates pass.

Possible requirements:

* Exchange testnet support
* Explicit user confirmation
* Maximum order size
* Daily loss circuit breaker
* Kill switch
* Order reconciliation
* Duplicate-order protection
* Position reconciliation
* Secure secret handling
* Full audit log

Real trading will remain a separate module from analysis.

---

# 36. Validation Gates

The project should not advance based only on subjective impressions.

## Gate 1 — Technical correctness

Required:

* Unit tests pass
* Integration tests pass
* No invalid numerical outputs
* Stable data retrieval
* Reproducible analysis

## Gate 2 — Historical viability

Required:

* Positive expectancy on selected test sets
* Acceptable drawdown
* Sufficient sample size
* Results not dependent on one symbol
* No obvious lookahead bias

## Gate 3 — Out-of-sample viability

Required:

* Performance remains acceptable on unseen periods
* Strategy behavior remains stable
* No severe score-band collapse

## Gate 4 — Forward paper viability

Required:

* Paper results broadly agree with modeled performance
* Slippage and timing do not destroy expectancy
* System operates reliably over an extended sample
* Failures are logged and recoverable

## Gate 5 — Execution readiness

Required before real orders:

* Risk controls cannot be bypassed accidentally
* Kill switch tested
* Duplicate-order protection tested
* Position reconciliation tested
* Maximum-loss controls tested
* Testnet execution validated

---

# 37. Performance Evaluation Principles

Apex will not be optimized only for win rate.

A strategy with a high win rate can still be poor if losses are much larger than wins.

Primary evaluation should consider:

* Expectancy
* Profit factor
* Drawdown
* Risk-adjusted return
* Stability across markets
* Stability across regimes
* Sensitivity to fees and slippage
* Number of opportunities
* Average holding time
* Tail losses

The best version is not necessarily the version with the most trades or the highest win rate.

The preferred version is the one with the strongest repeatable risk-adjusted expectancy.

---

# 38. Security

Even before real trading, the project should follow secure practices.

Rules:

* Never commit API keys
* Keep `.env` ignored
* Provide `.env.example` without secrets
* Use read-only credentials where possible
* Separate public-data and trading credentials
* Never log secrets
* Validate all configuration
* Use least-privilege access
* Keep execution disabled by default

---

# 39. Git and Repository Workflow

Repository:

```text
mshahwaiz-ali/apex
```

Visibility:

```text
private
```

Primary branch:

```text
main
```

Project workflow:

* Keep the architecture modular
* Add tests with every feature
* Keep commits focused
* Avoid unnecessary branches
* Preserve working behavior during refactors
* Do not mix large unrelated changes
* Update documentation when architecture or behavior changes
* Keep `plan.md` as the authoritative project roadmap

The project should remain easy to inspect and operate locally on Ubuntu using VS Code.

---

# 40. Initial Non-Goals

The first version will not include:

* Guaranteed profit claims
* Fully autonomous real-money trading
* Paid LLM dependence
* A heavy web framework
* Frappe dependency
* Complex distributed infrastructure
* Social sentiment scraping
* Unverified machine-learning models
* A mobile application
* Copy-trading functionality
* Martingale position sizing
* Unlimited leverage
* Averaging into losing positions without strict rules

These may only be reconsidered when the core engine is proven.

---

# 41. Final Product Vision

The mature Apex system should be able to:

1. Continuously ingest live multi-timeframe crypto data
2. Understand the broader market regime
3. Detect structure, liquidity, traps, momentum, and volatility
4. Generate multiple possible long and short candidates
5. Reject weak or unsafe candidates
6. Rank the strongest current opportunities
7. Produce actionable entries near the current price
8. Calculate structured stops, targets, sizing, and leverage
9. Explain every decision
10. Track performance through backtesting and paper trading
11. Improve through evidence rather than guesswork
12. Eventually support safe optional execution as a completely separate layer

The end goal is not a generic indicator dashboard.

The end goal is a disciplined, aggressive, testable crypto opportunity engine that actively searches for high-upside setups while preserving clear invalidation and controlled risk.

---

# 42. Immediate Next Step

The next implementation task is **Phase 0 — Repository Foundation**.

The first code milestone should establish:

* `pyproject.toml`
* Installable `src/apex` package
* Configuration system
* Logging system
* Core domain models
* CLI entry point
* Test configuration
* Formatting and linting
* Initial continuous-integration workflow
* A small smoke test proving the project works end to end

No strategy code should be added until this foundation is stable.
