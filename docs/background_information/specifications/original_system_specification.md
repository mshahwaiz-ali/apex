# Apex Trading Agent

## High-Leverage Futures Precision Trading System

Apex Trading Agent is a deterministic Python-based crypto futures analysis system designed to find high-quality, high-leverage trading opportunities with precise lower-timeframe entries.

The system is built for traders who want to:

* trade liquid crypto futures;
* use high leverage such as `10x–20x`;
* avoid entering too early or chasing price;
* calculate margin automatically;
* identify direction from higher timeframes;
* refine entries using `1m`, `3m`, and `5m` charts;
* scalp short-term moves;
* keep part of the position open when a larger move is developing;
* analyze both normal liquid coins and fast-moving top gainers;
* reduce unnecessary adverse movement after entry;
* improve results using backtesting, paper trading, and measurable evidence.

Apex is not intended to generate random long or short signals.

Its purpose is to answer:

> What is the best currently actionable high-leverage futures trade, where should it be entered, how much margin should be used, and when should the position be exited?

---

# 1. Final Product Scope

The first production direction of Apex will focus only on:

```text
Crypto perpetual futures
High-leverage trading
Isolated margin
Automatic margin calculation
Intraday and scalping setups
Multi-timeframe analysis
Normal market scanner
Top-gainer scanner
Manual symbol analysis
```

Spot trading is not part of the immediate implementation scope.

Real-money order execution is also not part of the initial scope.

The development sequence will be:

```text
Analysis
→ Backtesting
→ Live paper trading
→ Testnet
→ Optional real execution later
```

---

# 2. Core Trading Objective

The system should search for trades where:

* the broader direction is supported by higher timeframes;
* the entry is close to a meaningful invalidation level;
* immediate adverse movement is likely to remain limited;
* sufficient upside or downside remains available;
* the market is liquid enough for leverage;
* the trade has a clear target;
* the required margin does not expose the whole wallet;
* leverage is high, but account-level risk remains controlled.

Apex must optimize for:

```text
High-quality direction
+
Precise entry
+
Low adverse movement
+
High reward potential
+
Controlled wallet exposure
```

The system must not optimize only for win rate.

A setup that wins frequently but requires large adverse movement before moving into profit may still be unsuitable for high leverage.

---

# 3. Final Trading Model

## 3.1 Futures only

Apex will initially support perpetual futures only.

Every trade must use:

```text
Isolated margin
```

Cross margin must not be used because it can expose the rest of the wallet to the same position.

---

## 3.2 High leverage

Apex should support:

```text
Automatic leverage
Manual leverage
```

### Automatic leverage

The system should normally select leverage inside the configured high-leverage range.

Initial target:

```text
Minimum auto leverage: 10x
Preferred range: 10x–20x
```

The exact value should depend on:

* stop distance;
* coin volatility;
* spread;
* liquidity;
* market regime;
* entry precision;
* liquidation distance;
* exchange leverage limits.

Apex must not select leverage only because the user wants the highest available number.

The selected leverage must remain compatible with:

* the structural stop;
* the emergency stop;
* the liquidation buffer;
* the calculated margin.

### Manual leverage

The user may provide leverage manually.

Example:

```text
10x
15x
20x
25x
```

When manual leverage is selected, Apex should still calculate:

* safe margin amount;
* total position notional;
* estimated liquidation distance;
* stop compatibility;
* maximum planned loss;
* fee allowance;
* slippage allowance.

Manual leverage must not bypass safety calculations.

---

# 4. Automatic Margin Calculation

High leverage and high margin are separate decisions.

Apex should preserve high leverage while automatically limiting how much wallet balance is placed as margin.

The user should provide:

```text
Wallet balance
Leverage mode
Optional manual leverage
Maximum acceptable account loss
```

The system should calculate:

```text
Allowed loss amount
Stop distance
Maximum position notional
Required margin
Wallet exposure percentage
Estimated fees
Estimated slippage
Liquidation buffer
```

Basic position sizing model:

```text
Allowed Loss = Wallet Balance × Risk Percentage
```

```text
Position Notional = Allowed Loss ÷ Stop Distance Percentage
```

```text
Required Margin = Position Notional ÷ Leverage
```

Example:

```text
Wallet Balance: $100
Allowed Loss: $3
Stop Distance: 0.60%
Leverage: 20x
```

Calculation:

```text
Position Notional = 3 ÷ 0.006
                  = $500
```

```text
Required Margin = 500 ÷ 20
                = $25
```

Result:

```text
Wallet Balance: $100
Used Margin: $25
Position Notional: $500
Leverage: 20x
Maximum Planned Loss: approximately $3 plus fees and slippage
Unused Wallet Balance: $75
```

This allows aggressive leverage without placing the complete wallet at risk.

---

# 5. Risk Modes

The system should remain simple.

Instead of many complicated profiles, Apex should initially support three risk modes.

## 5.1 Standard

```text
Typical leverage: 10x–15x
Typical planned account loss: 1%–1.5%
```

Used for:

* early testing;
* normal liquid markets;
* average-quality valid setups;
* conservative paper trading.

## 5.2 Aggressive

```text
Typical leverage: 15x–20x
Typical planned account loss: 2%–3%
```

Used for:

* strong directional alignment;
* precise lower-timeframe entries;
* good liquidity;
* acceptable liquidation buffer;
* strong target space.

This should be the default intended Apex mode.

## 5.3 Extreme

```text
Leverage: high manual or exchange-dependent
Maximum planned account loss: configurable, initially capped
```

Used only when:

* the setup quality is exceptional;
* entry precision is strong;
* market liquidity is high;
* the stop is structurally valid;
* volatility is suitable;
* liquidation remains safely beyond the stop.

Extreme mode must not automatically use the entire wallet.

---

# 6. Coin Selection

Apex should support three analysis paths.

## 6.1 Manual symbol

The user provides a coin.

Example:

```bash
apex futures analyze SOL/USDT
```

The system performs the complete multi-timeframe analysis for that symbol.

---

## 6.2 Best normal-market coin

Apex scans a configured universe of liquid futures markets.

Possible initial universe:

```text
BTC/USDT
ETH/USDT
SOL/USDT
BNB/USDT
XRP/USDT
DOGE/USDT
ADA/USDT
AVAX/USDT
LINK/USDT
SUI/USDT
```

The exact list must remain configurable.

A normal-market coin should pass:

* minimum 24-hour volume;
* acceptable spread;
* sufficient recent movement;
* clean candle history;
* stable liquidity;
* sufficient target space;
* no abnormal data gaps;
* no excessive manipulation;
* supported futures market;
* valid order-size filters.

The scanner should return:

```text
Best normal-market opportunity
Backup normal-market opportunity
Rejected high-potential opportunities
```

---

## 6.3 Best top-gainer coin

Apex should separately scan top gainers.

The purpose is not to long every coin that has already pumped.

The purpose is to identify:

* fresh momentum;
* continuation;
* controlled pullback;
* exhaustion;
* distribution;
* breakdown;
* short opportunities after failed continuation.

Top-gainer selection should consider:

```text
24h percentage change
24h quote volume
5m return
15m return
30m return
Volume acceleration
Relative volume
Spread
Recent ATR expansion
Price stability
Futures liquidity
Current structure
```

A coin should not be selected only because it is ranked first by 24-hour percentage gain.

---

# 7. Normal Coins and Gainers Must Use Separate Logic

A normal liquid coin and a coin that has already pumped `20%–40%` should not be analyzed with identical thresholds.

Indicators such as:

* RSI;
* MACD;
* EMA distance;
* volatility;
* volume;

can remain extremely elevated during a genuine momentum expansion.

Therefore:

```text
High RSI does not automatically mean short.
Large EMA distance does not automatically mean reversal.
A 30% pump does not automatically mean the move is finished.
```

Apex must classify top gainers through a dedicated market-state model.

---

# 8. Gainer State Machine

Every selected gainer should be classified into one of these states:

```text
FRESH_BREAKOUT
ACCELERATION
CONTROLLED_CONTINUATION
FIRST_EXHAUSTION
DISTRIBUTION
BREAKDOWN
FAILED_BREAKDOWN_BOUNCE
TERMINAL_EXTENSION
CHAOTIC
```

## 8.1 Fresh breakout

Characteristics:

* new range breakout;
* strong but not terminal volume;
* sufficient target space;
* price holding above breakout;
* limited prior extension.

Preferred action:

```text
Long continuation or breakout retest
```

## 8.2 Acceleration

Characteristics:

* increasing candle range;
* increasing volume;
* strong trend;
* limited pullback;
* rapid short-timeframe movement.

Preferred action:

```text
Momentum long with strict chase protection
```

## 8.3 Controlled continuation

Characteristics:

* higher lows;
* shallow pullbacks;
* volume remains constructive;
* previous breakout remains valid;
* price consolidates above support.

Preferred action:

```text
Pullback continuation
```

## 8.4 First exhaustion

Characteristics:

* momentum begins slowing;
* new highs become weaker;
* volume climax may appear;
* wick size increases;
* local structure becomes unstable.

Preferred action:

```text
Do not immediately short.
Wait for structural failure.
```

## 8.5 Distribution

Characteristics:

* repeated failed highs;
* large sell reactions;
* lower highs;
* high volume without progress;
* support tests increase.

Preferred action:

```text
Prepare for short after confirmed breakdown or failed reclaim
```

## 8.6 Breakdown

Characteristics:

* local support breaks;
* volume supports the break;
* reclaim fails;
* lower high forms.

Preferred action:

```text
Short continuation
```

## 8.7 Terminal extension

Characteristics:

* extreme candle expansion;
* abnormal distance from support;
* late volume climax;
* poor entry geometry;
* unstable spread;
* insufficient safe stop.

Preferred action:

```text
No trade
```

---

# 9. Multi-Timeframe Model

Each timeframe must have a different responsibility.

Indicators should not be treated identically on every timeframe.

---

## 9.1 4-hour timeframe

Purpose:

```text
Macro structure
Major trend
Major support and resistance
Large liquidity levels
Broader target direction
Extension detection
```

Possible analysis:

* swing highs and lows;
* EMA 50 and EMA 200;
* ATR regime;
* major range boundaries;
* large-volume areas;
* major liquidity;
* macro trend strength.

The 4h timeframe should not define exact entries.

---

## 9.2 1-hour timeframe

Purpose:

```text
Directional permission
Intermediate structure
Trend health
Major continuation or reversal state
```

Possible analysis:

* EMA 20/50/200;
* MACD direction and histogram;
* RSI regime;
* structure;
* momentum slope;
* support and resistance;
* volume condition;
* extension.

The 1h timeframe should decide whether the system prefers:

```text
LONG
SHORT
BOTH
NO_DIRECTIONAL_PERMISSION
```

---

## 9.3 30-minute timeframe

Purpose:

```text
Intraday structure
Important pullback zones
Range boundaries
Breakout maturity
Liquidity levels
Volatility regime
```

Possible analysis:

* EMA 9/20/50;
* VWAP;
* RSI;
* MACD;
* ATR;
* relative volume;
* Fibonacci zones;
* structure;
* support and resistance.

---

## 9.4 15-minute timeframe

Purpose:

```text
Primary setup formation
```

The 15m chart should identify:

* trend pullback;
* breakout;
* breakout retest;
* liquidity sweep;
* range reversal;
* continuation;
* exhaustion;
* failed continuation;
* compression.

The 15m timeframe should provide the main setup thesis.

---

## 9.5 5-minute timeframe

Purpose:

```text
Entry construction
Local structure
Stop location
Momentum confirmation
```

Possible analysis:

* EMA 9/20;
* VWAP;
* fast RSI;
* relative volume;
* ATR;
* candle body and wick structure;
* local swings;
* micro support and resistance;
* local liquidity.

The 5m timeframe is especially important for normal liquid coins.

---

## 9.6 3-minute timeframe

Purpose:

```text
Primary entry refinement
```

The 3m chart should identify:

* liquidity sweeps;
* reclaim;
* retest;
* micro break of structure;
* momentum recovery;
* local failed breakdown;
* local failed breakout;
* stop geometry.

For top gainers, the 3m timeframe may become the primary entry chart.

---

## 9.7 1-minute timeframe

Purpose:

```text
Exact trigger
Immediate momentum
Chase protection
Fast-failure detection
```

The 1m timeframe should be used for:

* exact entry trigger;
* reclaim candle;
* retest;
* immediate rejection;
* entry cancellation;
* early exit.

The 1m timeframe must never define the complete directional thesis by itself.

---

# 10. Strategy-Regime Routing

Apex should not run every strategy equally in every market.

The system should first classify the market regime.

Possible regimes:

```text
STRONG_TREND
WEAK_TREND
CONTROLLED_PULLBACK
RANGE
COMPRESSION
BREAKOUT_EXPANSION
REVERSAL_TRANSITION
LIQUIDITY_SWEEP
MOMENTUM_GAINER
EXHAUSTION
HIGH_VOLATILITY_CHAOS
LOW_LIQUIDITY
```

Then select eligible strategies.

| Market Condition           | Preferred Strategy                |
| -------------------------- | --------------------------------- |
| Strong trend               | Trend pullback                    |
| Controlled pullback        | Pullback continuation             |
| Fresh breakout             | Breakout continuation             |
| Completed breakout         | Breakout retest                   |
| Liquidity sweep            | Sweep reversal                    |
| Stable range               | Range-edge reversal               |
| Compression                | Compression breakout              |
| Active gainer              | Momentum-gainer continuation      |
| Failed gainer continuation | Breakdown or failed-reclaim short |
| High-volatility chaos      | No trade                          |

Strategies not compatible with the detected regime should be disabled for that analysis.

---

# 11. Final Strategy Families

The initial production strategy set should include:

```text
TREND_PULLBACK
BREAKOUT_CONTINUATION
BREAKOUT_RETEST
LIQUIDITY_SWEEP_REVERSAL
RANGE_EDGE_REVERSAL
MOMENTUM_CONTINUATION
MOMENTUM_GAINER_CONTINUATION
COMPRESSION_BREAKOUT
FAILED_CONTINUATION_REVERSAL
GAINER_BREAKDOWN_SHORT
```

Each strategy should return:

```text
Direction
Setup type
Entry concept
Entry zone
Invalidation
Targets
Supporting evidence
Contradicting evidence
Required regime
Preferred timeframes
Entry trigger
Expiry condition
```

---

# 12. Entry System

Entry quality is the most important part of Apex.

The system should not only determine direction.

It should determine whether the current price is suitable for entry.

Possible entry states:

```text
WATCH
APPROACHING_ENTRY
READY_NOW
WAIT_FOR_RECLAIM
WAIT_FOR_RETEST
MISSED_ENTRY
INVALIDATED
NO_TRADE
```

---

## 12.1 Ready now

A trade may be marked `READY_NOW` only when:

* higher-timeframe direction is acceptable;
* the 15m setup is valid;
* the 5m or 3m entry structure is valid;
* the 1m chart is not excessively extended;
* spread is acceptable;
* stop placement is logical;
* liquidation remains beyond the stop;
* target space remains available;
* the current price is inside the approved entry zone.

---

## 12.2 Entry zone

Apex should return:

```text
Entry Zone Low
Entry Zone High
Ideal Entry
Maximum Chase Price
Current Price
Distance From Ideal Entry
```

Example:

```text
Current Price: 153.42
Entry Zone: 153.20–153.55
Ideal Entry: 153.31
Maximum Chase Price: 153.72
```

If price exceeds the maximum chase value:

```text
Status: MISSED_ENTRY
```

The system must not continue approving the trade after the risk-to-reward has significantly deteriorated.

---

# 13. Sweep Entry Design

Pure pre-sweep entry should not be the default.

A liquidity sweep may extend further than expected.

For high leverage, this can produce immediate adverse movement.

Apex should support two entry types.

---

## 13.1 Reclaim entry

Default entry method:

```text
Liquidity level reached
→ sweep or rejection
→ micro structure recovery
→ reclaim
→ optional retest
→ entry
```

Advantages:

* better confirmation;
* clearer invalidation;
* reduced probability of entering before a deeper sweep;
* better compatibility with high leverage.

---

## 13.2 Anticipation entry

Optional aggressive method:

```text
Enter inside or near the expected liquidity zone before full reclaim
```

Allowed only when:

* higher timeframes are strongly aligned;
* the level is structurally important;
* volatility is controlled;
* volume shows absorption;
* the setup score is exceptional;
* the stop remains valid;
* liquidation is safely beyond invalidation.

Anticipation entry should use smaller initial size.

Possible position split:

```text
Anticipation Entry: 25%–35%
Reclaim Entry: 65%–75%
```

This scaling method may be added after the basic reclaim system is validated.

The first stable version should use reclaim entries as the default.

---

# 14. Indicator Framework

Indicators should provide evidence.

They must not operate as a simple voting system.

---

## 14.1 Trend indicators

* EMA 9;
* EMA 20;
* EMA 50;
* EMA 200;
* EMA slope;
* price distance from EMA;
* VWAP;
* trend persistence;
* directional candle consistency.

---

## 14.2 Momentum indicators

* RSI;
* RSI slope;
* MACD;
* MACD histogram;
* rate of change;
* acceleration;
* deceleration;
* divergence candidates.

---

## 14.3 Volatility indicators

* ATR;
* ATR percentage;
* Bollinger Band width;
* candle expansion;
* candle compression;
* volatility percentile;
* wick abnormality;
* current range relative to history.

---

## 14.4 Volume indicators

* average volume;
* relative volume;
* volume spike;
* breakout volume;
* exhaustion volume;
* directional volume pressure;
* volume acceleration;
* volume without price progress.

---

## 14.5 Price-location indicators

* distance from support;
* distance from resistance;
* distance from recent swing;
* distance from VWAP;
* range position;
* Bollinger location;
* extension from EMA;
* remaining target space.

---

## 14.6 Fibonacci

Fibonacci should be used only as confluence.

Example:

```text
15m support
+
0.50–0.618 retracement
+
VWAP
+
EMA zone
+
3m liquidity sweep
+
3m reclaim
```

Fibonacci alone must not create a trade.

---

# 15. Precision Entry Scoring

Apex should not return only one confidence score.

Every setup should include independent scores.

```text
Direction Confidence
Setup Quality
Entry Precision
Immediate Adverse-Move Risk
Liquidity Quality
Regime Fit
Momentum Quality
Volume Quality
Risk Geometry
Target Quality
Data Confidence
Final Trade Quality
```

Example:

```text
Direction Confidence: 87
Setup Quality: 86
Entry Precision: 92
Immediate Adverse-Move Risk: 18
Liquidity Quality: 89
Regime Fit: 91
Risk Geometry: 84
Final Trade Quality: 88
```

For adverse-move risk:

```text
Lower is better
```

Example initial high-leverage requirements:

```text
Final Trade Quality >= 80
Entry Precision >= 82
Risk Geometry >= 78
Data Confidence >= 85
Immediate Adverse-Move Risk <= 30
```

These values are starting points.

They must later be calibrated through testing.

---

# 16. Stop and Invalidation Model

Apex should use three exit protection concepts.

## 16.1 Soft failure exit

Used when the setup quality collapses before the structural stop.

Examples:

* reclaim fails immediately;
* two consecutive 1m candles lose the entry level;
* volume disappears;
* micro structure reverses;
* BTC moves sharply against the trade;
* the entry thesis is no longer valid.

The soft exit may reduce loss before the hard stop.

---

## 16.2 Structural stop

The level where the trade thesis becomes invalid.

Possible references:

* sweep extreme;
* swing high or low;
* failed retest level;
* range boundary;
* breakout failure point;
* ATR-adjusted structure level.

The structural stop must not be placed randomly.

---

## 16.3 Emergency exchange stop

A hard protective stop placed on the exchange.

Used for:

* connection failure;
* sudden violent movement;
* software failure;
* extreme slippage;
* unexpected market event.

The emergency stop must remain beyond normal noise but before liquidation.

---

# 17. Liquidation Safety

Apex must estimate liquidation distance before approving any futures trade.

A trade should be rejected when:

* liquidation is inside the structural stop;
* liquidation is too close to the stop;
* exchange maintenance margin makes the geometry unsafe;
* the selected leverage does not leave sufficient buffer;
* the coin is too volatile for the chosen leverage;
* spread and slippage invalidate the buffer.

The exact liquidation calculation should later use exchange-specific formulas.

Until then, the engine should use conservative estimates.

---

# 18. Profit-Taking Model

Apex is designed for scalping, but it should allow larger moves to continue.

Default position management:

```text
TP1: close 40%
TP2: close 35%
Runner: keep 25%
```

Percentages must remain configurable.

---

## 18.1 TP1

Purpose:

* secure early profit;
* reduce position exposure;
* improve psychological and capital stability.

---

## 18.2 TP2

Purpose:

* capture the main expected move;
* realize most of the planned reward.

---

## 18.3 Runner

Purpose:

* remain exposed when a larger trend continuation develops;
* capture extended gainers;
* capture larger higher-timeframe targets.

Runner stop management may use:

* trailing structure;
* EMA;
* VWAP;
* new swing low or high;
* ATR trail;
* target-specific rules.

A stop should not automatically move to breakeven immediately after TP1 if normal volatility is likely to retest the entry.

---

# 19. Trade Lifecycle

Every setup should move through a defined lifecycle.

```text
GENERATED
WATCHING
APPROACHING_ENTRY
READY_NOW
ENTERED
PARTIALLY_CLOSED
RUNNER_ACTIVE
STOPPED
TARGET_HIT
SOFT_EXITED
MISSED
EXPIRED
CANCELLED
INVALIDATED
```

A setup should expire when:

* entry is not reached within its configured lifetime;
* price reaches the target before entry;
* structural conditions change;
* market regime changes;
* current price exceeds the maximum chase level;
* spread becomes unacceptable;
* data becomes stale;
* market-wide direction changes materially.

---

# 20. Output Format

A futures setup should return:

```json
{
  "symbol": "SOL/USDT",
  "market_mode": "FUTURES",
  "margin_mode": "ISOLATED",
  "status": "READY_NOW",
  "decision": "LONG",
  "strategy": "trend_pullback_reclaim",
  "market_category": "NORMAL",
  "current_price": 153.42,
  "entry": {
    "zone_low": 153.20,
    "zone_high": 153.55,
    "ideal": 153.31,
    "maximum_chase": 153.72,
    "trigger": "3m liquidity reclaim and 1m retest"
  },
  "stop": {
    "soft_failure_level": 153.02,
    "structural_stop": 152.48,
    "emergency_stop": 152.38
  },
  "targets": [
    {
      "label": "TP1",
      "price": 154.72,
      "close_percentage": 40
    },
    {
      "label": "TP2",
      "price": 156.10,
      "close_percentage": 35
    },
    {
      "label": "RUNNER",
      "price": 158.80,
      "close_percentage": 25
    }
  ],
  "leverage": {
    "mode": "AUTO",
    "selected": 20,
    "minimum": 10,
    "maximum": 20
  },
  "account": {
    "wallet_balance": 100,
    "planned_loss": 3,
    "required_margin": 25,
    "position_notional": 500,
    "wallet_exposure_percentage": 25
  },
  "scores": {
    "direction_confidence": 87,
    "setup_quality": 86,
    "entry_precision": 92,
    "immediate_adverse_risk": 18,
    "risk_geometry": 84,
    "final_trade_quality": 88
  },
  "timeframe_bias": {
    "4h": "bullish",
    "1h": "bullish",
    "30m": "bullish_pullback",
    "15m": "support_reclaim",
    "5m": "entry_forming",
    "3m": "reclaim_confirmed",
    "1m": "retest_valid"
  },
  "supporting_evidence": [],
  "contradictions": [],
  "warnings": [],
  "invalidation_conditions": []
}
```

---

# 21. Scanner Output

The scanner should return three major sections:

```text
Best Overall Trade
Best Top-Gainer Trade
Best Normal-Market Trade
```

Optional backup:

```text
Backup Trade
```

Example:

```text
BEST OVERALL

Symbol: SOL/USDT
Category: Normal Market
Direction: LONG
Status: READY_NOW
Final Quality: 88
Leverage: 20x
Margin: $25
```

```text
BEST GAINER

Symbol: XYZ/USDT
Gainer State: Controlled Continuation
Direction: LONG
Status: APPROACHING_ENTRY
Final Quality: 84
```

```text
BEST NORMAL MARKET

Symbol: ETH/USDT
Direction: SHORT
Status: WAIT_FOR_RETEST
Final Quality: 82
```

The scanner should not force three trades if only one market has acceptable geometry.

---

# 22. Market-Wide Context

Apex should consider broader market conditions before approving altcoin trades.

Initial context:

* BTC direction;
* ETH direction;
* BTC volatility;
* market-wide risk state;
* abnormal broad sell-off;
* abnormal broad squeeze;
* correlation with BTC;
* major market support and resistance.

Later optional inputs:

* funding rate;
* open interest;
* liquidation clusters;
* market breadth;
* BTC dominance;
* economic-event risk;
* exchange-specific market pressure.

Market context should adjust setup confidence.

It must not directly override a valid structural stop.

---

# 23. Fundamental and Event-Risk Inputs

For intraday futures trading, useful fundamental inputs include:

* token unlocks;
* exchange listings;
* exchange delistings;
* protocol exploits;
* regulatory announcements;
* major network upgrades;
* scheduled economic events;
* major Bitcoin-related events;
* project announcements;
* abnormal news activity.

Event analysis should operate as a risk filter.

Example:

```text
Technical setup is valid.
Major scheduled event begins in five minutes.
Result: reduce score, reduce position size, or reject the setup.
```

Fundamental or news inputs must not independently create a trade.

---

# 24. Maximum Adverse Excursion

Apex must track Maximum Adverse Excursion.

MAE measures how far price moved against a trade after entry.

Example:

```text
Entry: 100
Lowest price after long entry: 99.60
MAE: 0.40%
```

This metric is critical for high-leverage entry quality.

The system should report:

* average MAE;
* median MAE;
* winning-trade MAE;
* losing-trade MAE;
* 75th percentile MAE;
* 90th percentile MAE;
* MAE by strategy;
* MAE by timeframe trigger;
* MAE by market regime;
* MAE by leverage;
* MAE by entry type.

---

# 25. Maximum Favorable Excursion

Apex must also track Maximum Favorable Excursion.

MFE measures the maximum movement in the trade direction.

The engine should compare:

```text
MAE versus MFE
```

Preferred setup behavior:

```text
Low MAE
High MFE
Positive expectancy
Acceptable drawdown
```

This is more useful than judging entry quality only by whether the trade eventually won.

---

# 26. Backtesting Requirements

The backtester must simulate chronological behavior without future-data leakage.

Required behavior:

* historical candle loading;
* multi-timeframe synchronization;
* analysis using only data available at that time;
* signal generation;
* setup expiry;
* entry-zone simulation;
* stop simulation;
* target simulation;
* partial exits;
* runner behavior;
* fees;
* slippage;
* funding where applicable;
* conservative intrabar rules;
* leverage;
* liquidation estimation;
* margin usage;
* soft failure exits;
* missed trades;
* chase rejection.

When stop and target both appear inside the same candle, the system must not automatically assume the profitable result.

Use a conservative execution model.

---

# 27. Backtesting Metrics

Reports should include:

```text
Total trades
Winning trades
Losing trades
Breakeven trades
Win rate
Net return
Profit factor
Expectancy
Maximum drawdown
Average win
Average loss
Average risk-to-reward
Average holding time
Average MAE
Average MFE
Median MAE
Median MFE
Consecutive wins
Consecutive losses
Liquidation count
Soft-exit count
Stop count
Target count
Missed-entry count
Expired-setup count
```

Performance must be broken down by:

```text
Symbol
Strategy
Market category
Market regime
Direction
Timeframe trigger
Entry type
Score band
Leverage band
Margin percentage
Gainer state
Normal versus gainer
```

---

# 28. Accuracy Evaluation

The system may target high precision, but it must not be optimized only around:

```text
8 wins out of 10
```

A useful strategy must also maintain:

* positive expectancy;
* acceptable drawdown;
* sufficient sample size;
* realistic fees and slippage;
* stable results across multiple symbols;
* stable out-of-sample behavior;
* low liquidation frequency;
* controlled MAE.

A strategy with:

```text
80% win rate
```

may still be poor if:

```text
average loss is much larger than average win
```

or:

```text
winning trades regularly move too far against the entry
```

The preferred strategy is the one with the best repeatable risk-adjusted performance.

---

# 29. Dataset System

Before serious optimization, Apex must build reproducible historical datasets.

Required candle timeframes:

```text
1m
3m
5m
15m
30m
1h
4h
```

Where possible, larger timeframes should be constructed from consistent lower-timeframe data.

Dataset records may also include:

* ticker price;
* spread;
* quote volume;
* funding rate;
* open interest;
* BTC context;
* ETH context;
* market category;
* 24h gainer rank;
* exchange metadata.

Datasets should be stored in:

```text
Parquet
```

or:

```text
CSV for smaller experiments
```

Metadata must include:

* provider;
* symbol;
* market type;
* collection time;
* start and end time;
* missing intervals;
* data quality status.

---

# 30. Validation Stages

## Stage 1 — Technical correctness

Required:

* tests pass;
* configuration validates;
* indicators are deterministic;
* candle data is valid;
* no NaN or infinite output;
* strategy results are reproducible;
* position sizing is correct;
* leverage calculation is correct.

## Stage 2 — Historical baseline

Required:

* multiple symbols;
* multiple regimes;
* realistic fees;
* realistic slippage;
* minimum trade sample;
* no lookahead leakage;
* performance by strategy.

## Stage 3 — Out-of-sample validation

Required:

* unseen data periods;
* no threshold retuning during test;
* stable performance;
* stable MAE;
* acceptable drawdown.

## Stage 4 — Walk-forward testing

Required:

```text
Train
→ Validate
→ Move forward
→ Repeat
```

## Stage 5 — Live paper trading

Required:

* live data;
* original signal timestamp;
* actual entry availability;
* setup expiry;
* real spread;
* paper slippage;
* live MAE and MFE;
* daily performance reports.

## Stage 6 — Testnet

Required:

* real exchange filters;
* leverage configuration;
* isolated margin;
* stop placement;
* take-profit placement;
* partial exits;
* exchange rejection handling;
* duplicate-order protection;
* reconnect behavior;
* position reconciliation;
* emergency kill switch.

---

# 31. Revised Architecture

```text
apex/
├── README.md
├── pyproject.toml
├── .env.example
├── config/
│   ├── default.yaml
│   ├── futures.yaml
│   ├── symbols.yaml
│   ├── strategies.yaml
│   ├── gainers.yaml
│   ├── risk.yaml
│   └── backtesting.yaml
├── src/
│   └── apex/
│       ├── application/
│       ├── backtesting/
│       ├── cli/
│       ├── config/
│       ├── data/
│       ├── datasets/
│       ├── domain/
│       ├── entries/
│       ├── execution/
│       ├── features/
│       ├── gainers/
│       ├── liquidity/
│       ├── market_context/
│       ├── monitoring/
│       ├── optimization/
│       ├── paper_trading/
│       ├── reporting/
│       ├── risk/
│       ├── scanner/
│       ├── scoring/
│       ├── strategies/
│       ├── structure/
│       └── timeframe/
├── tests/
│   ├── backtesting/
│   ├── fixtures/
│   ├── integration/
│   ├── regression/
│   └── unit/
├── data/
│   ├── cache/
│   ├── datasets/
│   ├── paper_trading/
│   ├── reports/
│   └── testnet/
└── logs/
```

---

# 32. Important Domain Models

The revised system should include models such as:

```text
FuturesAccount
FuturesRiskMode
LeverageMode
MarginCalculation
LiquidationEstimate
MarketCategory
GainerState
MarketRegime
TimeframeRole
EntryState
EntryPlan
EntryTrigger
TradeCandidate
TradeSetup
StopPlan
TargetPlan
PositionPlan
TradeLifecycle
MarketContext
BacktestTrade
PaperTrade
```

---

# 33. Configuration Example

```yaml
futures:
  enabled: true
  margin_mode: isolated

  leverage:
    mode: auto
    auto_minimum: 10
    auto_maximum: 20
    manual_allowed: true

  risk:
    default_mode: aggressive

    standard:
      max_account_loss_percent: 1.5

    aggressive:
      max_account_loss_percent: 3.0

    extreme:
      max_account_loss_percent: 4.0

  margin:
    max_wallet_margin_percent: 35
    include_fees: true
    include_slippage: true

  entry:
    default_type: reclaim
    anticipation_enabled: false
    maximum_chase_atr_multiple: 0.25

  exits:
    tp1_close_percent: 40
    tp2_close_percent: 35
    runner_percent: 25

  liquidation:
    minimum_stop_buffer_percent: 0.40

scanner:
  manual_enabled: true
  normal_market_enabled: true
  gainer_enabled: true

  output:
    best_overall: 1
    best_normal: 1
    best_gainer: 1
    backups: 1
```

All values are initial defaults and must later be calibrated through testing.

---

# 34. CLI Direction

Possible commands:

```bash
apex futures analyze SOL/USDT
```

```bash
apex futures analyze SOL/USDT --wallet 100
```

```bash
apex futures analyze SOL/USDT \
  --wallet 100 \
  --risk aggressive \
  --leverage auto
```

```bash
apex futures analyze SOL/USDT \
  --wallet 100 \
  --leverage manual \
  --leverage-value 20
```

```bash
apex futures scan
```

```bash
apex futures scan --category normal
```

```bash
apex futures scan --category gainers
```

```bash
apex backtest run \
  --strategy momentum-gainer-continuation \
  --dataset data/datasets/gainers.parquet
```

```bash
apex paper start
```

```bash
apex paper report
```

---

# 35. Implementation Roadmap

## Phase 1 — Freeze the futures contract

Implement:

* futures-only mode;
* isolated margin;
* leverage mode;
* risk mode;
* wallet balance input;
* entry states;
* position plan;
* target plan;
* stop plan;
* trade lifecycle.

Completion criteria:

* configurations validate;
* domain models exist;
* CLI accepts futures account inputs;
* no strategy behavior changes yet.

---

## Phase 2 — Rewrite leverage and margin calculation

Implement:

* automatic leverage;
* manual leverage validation;
* account-loss-based position sizing;
* required margin;
* wallet exposure;
* fees;
* slippage allowance;
* liquidation estimate;
* unsafe trade rejection.

Completion criteria:

* correct calculations;
* invariant tests pass;
* leverage cannot bypass margin limits;
* margin cannot exceed configured wallet percentage.

---

## Phase 3 — Separate normal and gainer scanners

Implement:

* normal liquid universe;
* exchange top-gainer source;
* 24h volume filter;
* recent-return filter;
* spread filter;
* volatility filter;
* market-category model;
* scanner ranking.

Completion criteria:

* normal and gainer symbols are classified separately;
* one failed symbol does not stop the scanner;
* scanner provides best candidates from both categories.

---

## Phase 4 — Build the gainer state machine

Implement:

* fresh breakout;
* acceleration;
* controlled continuation;
* exhaustion;
* distribution;
* breakdown;
* bounce;
* terminal extension;
* chaotic state.

Completion criteria:

* fixture tests exist for each state;
* gainer strategy eligibility uses state;
* high RSI alone cannot create a short.

---

## Phase 5 — Build the precision-entry engine

Implement:

* entry zone;
* ideal entry;
* maximum chase;
* reclaim trigger;
* retest trigger;
* 5m structure;
* 3m refinement;
* 1m trigger;
* fast failure;
* setup expiry;
* entry precision score;
* immediate adverse-risk score.

Completion criteria:

* READY_NOW requires valid geometry;
* missed entries cannot remain active;
* low-timeframe trigger cannot override severe higher-timeframe conflict.

---

## Phase 6 — Improve strategy-regime routing

Implement:

* regime classification;
* strategy eligibility;
* normal versus gainer routing;
* breakout retest;
* compression breakout;
* failed continuation;
* gainer breakdown short.

Completion criteria:

* incompatible strategies do not run;
* every candidate explains why it was eligible;
* every rejected strategy explains the regime mismatch.

---

## Phase 7 — Implement scalp and runner lifecycle

Implement:

* TP1;
* TP2;
* runner;
* configurable percentages;
* soft exit;
* hard stop;
* emergency stop;
* runner trailing logic;
* partial-close state.

Completion criteria:

* lifecycle transitions are deterministic;
* partial exits are included in backtesting;
* runner results are measured separately.

---

## Phase 8 — Build historical datasets

Implement:

* multi-timeframe candle collection;
* synchronization;
* caching;
* Parquet export;
* gainer metadata;
* normal-market metadata;
* BTC market context;
* data-quality checks.

Completion criteria:

* datasets are reproducible;
* no missing timestamps remain unreported;
* backtesting can run offline.

---

## Phase 9 — Build the complete backtest campaign

Run:

* strategy-specific tests;
* normal-market tests;
* gainer tests;
* long and short tests;
* leverage-band tests;
* entry-type tests;
* score-band tests;
* regime tests.

Completion criteria:

* baseline report exists;
* MAE and MFE are available;
* fees and slippage are included;
* no strategy is promoted only because of win rate.

---

## Phase 10 — Calibration

Optimize:

* strategy thresholds;
* score weights;
* regime eligibility;
* entry trigger;
* chase limit;
* stop buffer;
* TP percentages;
* runner rules;
* leverage range.

Rules:

* change one variable group at a time;
* compare against baseline;
* reject overfitted improvements;
* preserve out-of-sample data;
* do not automatically rewrite production configuration.

---

## Phase 11 — Live paper trading

Implement:

* continuous scan;
* signal storage;
* live entry monitoring;
* setup expiry;
* soft failure;
* stop and target monitoring;
* MAE and MFE;
* daily reports;
* performance history.

Completion criteria:

* stable continuous operation;
* no duplicate trades;
* live signals match stored analysis;
* results can be audited.

---

## Phase 12 — Testnet futures

Implement:

* exchange-specific testnet adapter;
* order-size filters;
* leverage setting;
* isolated margin setting;
* market or limit entries;
* stop order;
* take profits;
* partial close;
* position reconciliation;
* duplicate-order protection;
* kill switch;
* execution audit.

Real-money execution remains disabled.

---

# 36. Quality Requirements

The project should use:

```text
Python 3.11+
Type hints
Pydantic models
Modular architecture
Small testable functions
Ruff
Strict mypy
Pytest
Coverage
Structured logging
Configuration-driven behavior
```

The project should avoid:

```text
Large monolithic files
Indicator voting
Hardcoded secrets
Cross-margin defaults
Full-wallet margin defaults
Unexplained score constants
Silent exception handling
Future-data leakage
Automatic real execution
Unlimited leverage assumptions
```

---

# 37. Critical Invariants

The system must enforce:

```text
Long stop < long entry
Short stop > short entry
Long targets > long entry
Short targets < short entry
Required margin <= configured wallet exposure
Planned loss <= configured account loss
Liquidation remains beyond emergency stop
No result contains NaN
No result contains infinity
No stale data produces READY_NOW
No MISSED_ENTRY setup can be entered
No cross-margin trade can be approved
No unsupported leverage can be selected
No strategy can bypass risk validation
```

---

# 38. Final Product Behavior

Apex should eventually provide an output like:

```text
APEX HIGH-LEVERAGE FUTURES SETUP

Symbol: SOL/USDT
Category: Normal Market
Status: READY_NOW
Direction: LONG
Strategy: 15m Trend Pullback + 3m Liquidity Reclaim

Current Price: 153.42
Entry Zone: 153.20–153.55
Ideal Entry: 153.31
Maximum Chase: 153.72

Soft Failure: 153.02
Structural Stop: 152.48
Emergency Stop: 152.38

TP1: 154.72 — Close 40%
TP2: 156.10 — Close 35%
Runner: 158.80 — Keep 25%

Wallet Balance: $100
Risk Mode: Aggressive
Auto Leverage: 20x
Required Margin: $25
Position Notional: $500
Maximum Planned Loss: approximately $3 plus costs

Direction Confidence: 87
Setup Quality: 86
Entry Precision: 92
Immediate Adverse Risk: 18
Risk Geometry: 84
Final Trade Quality: 88

4h: Bullish
1h: Bullish
30m: Controlled Pullback
15m: Support Reclaim
5m: Entry Structure Valid
3m: Liquidity Reclaim Confirmed
1m: Retest Valid

Do Not Enter Above: 153.72
Cancel If: BTC loses its 15m support before entry
```

---

# 39. Final Development Priority

The immediate priority is not to add more indicators.

The correct order is:

```text
1. Correct leverage and margin geometry
2. Separate normal coins and gainers
3. Build precise entry logic
4. Add entry quality and adverse-risk scoring
5. Improve strategy-regime routing
6. Add scalp and runner management
7. Build datasets
8. Backtest
9. Calibrate
10. Paper trade
11. Testnet
```

---

# 40. Final Design Principle

Apex should preserve high leverage.

It should not preserve full-wallet exposure.

The final system principle is:

> Select the strongest liquid futures opportunity, determine direction from higher timeframes, refine the entry using lower timeframes, minimize expected adverse movement, calculate margin automatically, keep liquidation beyond invalidation, secure scalp profits, and retain a runner when a larger move remains likely.

The goal is not to generate many trades.

The goal is to identify the most actionable high-leverage trade available under the current market conditions and explain exactly why it is valid.
