# Apex Trading Agent — Stage 3

## Trade Discovery Core Simplification and Complete Redesign

## 1. Final Product Definition

Apex ka abhi sirf ek primary purpose hoga:

> Binance USDT perpetual-futures market ko scan karna, current ya near-current price par available long aur short trade setups identify karna, unhein transparent scoring ke through rank karna, aur har selected setup ke liye complete entry, invalidation, stop-loss, targets, continuation guidance aur exit plan dena.

Apex abhi:

* wallet-management system nahi hoga;
* funded-account manager nahi hoga;
* leverage calculator nahi hoga;
* exchange execution system nahi hoga;
* paper-trading platform nahi hoga;
* autonomous optimization system nahi hoga;
* historical research command suite nahi hoga;
* reporting or operational-review platform nahi hoga.

Current active product surface ka focus sirf hoga:

```text
Find trade opportunities
→ evaluate them deeply
→ rank them
→ explain them
→ construct usable trade plans
```

---

# 2. Core Product Principle

Trade pehle market structure aur measurable evidence se discover hogi.

Wallet, risk allowance, leverage, margin allocation ya account size trade ko discover, reject, score ya rank nahi karega.

Required workflow:

```text
Discover futures universe
→ screen every eligible market
→ shortlist approximately 30 symbols
→ run detailed analysis
→ evaluate all applicable strategies
→ construct long and short candidates
→ score and rank candidates
→ display the best 15–20 available setups
→ log every calculation and decision
```

The scanner must answer:

1. Abhi kaunsa symbol tradeable movement dikha raha hai?
2. Direction long hai ya short?
3. Direction ka measurable reason kya hai?
4. Entry current price ke qareeb kahan hai?
5. Better retracement entry available hai ya nahi?
6. Setup kis price par invalid hoga?
7. Structural stop-loss kahan hai?
8. TP1, TP2 aur TP3 kahan hain?
9. TP1 ke baad hold karna ho to kya condition observe karni hai?
10. Momentum continue ho raha hai ya exit karna better hai?
11. Setup kitna strong, aggressive, late ya uncertain hai?
12. Is setup ke fail hone ke primary risks kya hain?

---

# 3. Decisions Locked for Stage 3

## 3.1 Futures only

Active market:

```text
Binance USDT perpetual futures
```

Only contracts satisfying all of these are eligible:

* quote asset is USDT;
* contract type is perpetual;
* exchange status is actively trading;
* valid price and quantity filters exist;
* recent ticker and candle data are available;
* spread and liquidity are measurable;
* sufficient recent history exists.

Delivery contracts, inactive contracts, spot pairs and non-USDT products are excluded.

---

## 3.2 Only two scanning modes

### Broad Market Scan

```bash
apex scan
```

Behavior:

* dynamically discover all active Binance USDT perpetual contracts;
* run lightweight screening over the complete eligible universe;
* shortlist the best approximately 30 symbols;
* run full detailed analysis on the shortlist;
* display the best 15–20 trade candidates.

### Manual Symbol Analysis

```bash
apex analyze SYMBOL
```

Behavior:

* analyze one requested futures symbol deeply;
* evaluate every applicable long and short strategy;
* display the primary setup and useful alternatives;
* show complete calculations, evidence, targets and exit guidance.

No separate normal mode, gainer mode, fast-gainer mode, funded mode, paper mode or spot scan mode.

---

## 3.3 Risk profile completely removed from trade discovery

Remove from active scanner and analyzer:

* wallet balance;
* risk profile;
* Standard mode;
* Funded mode;
* Aggressive mode;
* Extreme mode;
* maximum planned loss;
* risk-per-trade percentage;
* account drawdown;
* daily loss limit;
* margin allocation;
* isolated/cross selection;
* leverage mode;
* position quantity;
* position notional;
* liquidation planning;
* risk feasibility score;
* rejection caused by insufficient wallet risk.

Remove output blocks such as:

```text
Risk Profile
Wallet
Risk mode
Maximum planned loss
Margin mode
Leverage mode
```

A message such as:

```text
A setup formed but did not meet the required quality or risk standards
```

must disappear.

A setup can be weak because of its **market evidence, structure, timing, liquidity or target geometry**, but not because the configured wallet only permits a `0.25 USDT` loss.

Structural stop-loss remains mandatory because it belongs to the trade thesis—not the wallet profile.

---

## 3.4 Leverage postponed

Leverage does not belong in Stage 3.

Stage 3 returns:

* entry;
* invalidation;
* stop;
* targets;
* percentage distance to stop;
* reward-to-risk geometry.

It does not decide:

* position size;
* leverage;
* margin;
* wallet exposure;
* liquidation price.

A separate optional execution-sizing module may be designed later after trade discovery quality is proven.

---

## 3.5 Spot frozen

Spot code must not be expanded during Stage 3.

For now:

* unregister spot commands;
* remove spot from active README and help;
* exclude spot tests from the active redesign surface where safe;
* preserve reusable indicator, feature and strategy logic;
* do not build a separate spot architecture.

Later, spot should reuse the same discovery and strategy engine with a spot-specific trade-plan adapter.

---

## 3.6 Paper trading and execution removed from active product

Unregister from the default CLI:

* paper commands;
* paper scheduler;
* paper pipeline;
* paper daily reports;
* paper intake;
* paper status;
* testnet execution;
* kill-switch commands;
* readiness commands;
* funded-history commands;
* operational validation commands.

Reusable storage or historical simulation primitives may remain internally until dependency tracing is complete.

They must not control or complicate live scanning.

---

## 3.7 Historical research reduced to internal tooling

Stage 3 is not primarily a backtesting or dataset-management product.

Keep only components that directly help:

* replay a strategy;
* compare later market outcome with scan output;
* measure candidate accuracy;
* inspect false positives and false negatives;
* calibrate manually.

Large campaign orchestration, milestone reviews, research overlays, evidence ceremonies and duplicated historical commands should be archived or removed after dependency verification.

---

# 4. Realistic Accuracy Objective

The system may aim to produce:

```text
15–20 visible candidates per broad scan
```

However, these must not all be presented as equally strong trades.

The final results should be ranked and labelled, for example:

* top-quality actionable;
* strong but aggressive;
* pullback preferred;
* speculative;
* watch-only;
* late or chasing.

The goal of `90% correct trades` cannot be treated as a guaranteed acceptance criterion.

A useful engineering objective is:

> Continuously reduce avoidable false positives and improve the precision of the highest-ranked candidates through logged evidence and historical comparison.

Accuracy must be evaluated separately for:

* direction correctness;
* entry reached;
* TP1 reached before stop;
* TP2 reached before stop;
* maximum favorable excursion;
* maximum adverse excursion;
* strategy type;
* score band;
* market regime;
* holding horizon.

The highest-ranked five setups should eventually demonstrate better measured performance than lower-ranked candidates. That ranking quality is more valuable than artificially claiming that 90% of all displayed trades are winners.

---

# 5. Target Architecture

```text
Binance Futures Metadata
        ↓
Eligible USDT Perpetual Universe
        ↓
Batch Ticker and Lightweight Candle Collection
        ↓
Market-Wide Opportunity Features
        ↓
Opportunity Scoring
        ↓
Top 30 Symbol Shortlist
        ↓
Detailed Multi-Timeframe Features
        ↓
Market-State Classification
        ↓
Applicable Long and Short Strategies
        ↓
Candidate Construction
        ↓
Setup and Timing Scoring
        ↓
Entry, Stop, Targets and Exit Guidance
        ↓
Cross-Symbol Ranking
        ↓
Top 15–20 Results
        ↓
Structured Diagnostic Log
```

The architecture must keep these modules separate:

```text
providers
universe
screening
features
market_state
strategies
candidates
entries
targets
scoring
ranking
presentation
logging
```

No module should combine the entire pipeline in one large function.

---

# 6. Dynamic Binance Futures Universe

## 6.1 Contract metadata

Use Binance futures exchange metadata to collect:

* symbol;
* base asset;
* quote asset;
* contract type;
* trading status;
* tick size;
* quantity step size;
* minimum quantity;
* minimum notional where applicable;
* price precision;
* quantity precision.

## 6.2 Dynamic selection

Static `symbols.yaml` must no longer be the primary source for broad scans.

It may remain only for:

* manual allowlists;
* temporary testing;
* explicit symbol overrides;
* blacklists.

## 6.3 Early eligibility checks

Exclude only markets that are genuinely unsuitable:

* inactive contract;
* invalid metadata;
* no usable ticker;
* no usable candles;
* excessive spread;
* severely inadequate liquidity;
* broken or stale market data;
* newly listed market without enough required history;
* manually blacklisted symbol.

Do not reject a symbol merely because:

* 24-hour volume is not among the highest;
* higher timeframe opposes the immediate move;
* the market is volatile;
* it is not already a top gainer.

---

# 7. Broad Market Opportunity Screening

The broad screener does not generate the final trade.

It answers:

> Which symbols deserve expensive detailed analysis right now?

## 7.1 Screening universe

The screener runs once per eligible contract.

No symbol is duplicated into separate normal and gainer categories.

## 7.2 Lightweight inputs

Prefer batch ticker endpoints and a small recent candle sample.

Calculate:

### Liquidity

* 24-hour quote volume;
* recent quote volume;
* trade count where available;
* bid-ask spread percentage;
* recent candle participation;
* volume consistency.

### Movement

* 5-minute return;
* 15-minute return;
* 30-minute return;
* 1-hour return;
* 4-hour contextual return;
* 24-hour return;
* absolute and directional movement.

### Acceleration

* change in return velocity;
* change in volume;
* expanding candle ranges;
* directional persistence;
* recent impulse versus prior baseline.

### Volatility

* ATR percentage;
* realized range;
* current range versus baseline;
* compression ratio;
* expansion ratio;
* noise and wick ratio.

### Structure proximity

* distance from recent high;
* distance from recent low;
* distance from local breakout boundary;
* distance from VWAP;
* distance from selected EMAs;
* distance from recent support or resistance.

### Freshness

* bars since expansion began;
* bars since breakout;
* bars since volume spike;
* move extension from origin;
* remaining nearby target space.

## 7.3 Opportunity score

Every eligible symbol receives a `0–100` opportunity score.

Suggested composition:

```text
movement potential
+ acceleration
+ relative volume
+ directional persistence
+ structure proximity
+ volatility usability
+ entry freshness
+ liquidity
- spread penalty
- exhaustion penalty
- chaotic-noise penalty
- stale-move penalty
```

All components and raw values must be logged.

## 7.4 Shortlist construction

Default:

```text
Eligible universe: all active USDT perpetual contracts
Detailed shortlist: 30 symbols
Final visible candidates: 15–20
```

The shortlist should not consist only of the largest 24-hour gainers.

It should preserve high-ranking opportunities across:

* emerging longs;
* emerging shorts;
* breakouts;
* failed breakouts;
* controlled pullbacks;
* reversals;
* compression releases;
* high-momentum scalps.

---

# 8. Capturing a Coin Before It Becomes a Top Gainer

A future gainer is usually visible through a combination of early changes—not a single indicator.

The screener must calculate a dedicated **early-expansion feature group**:

* rising short-timeframe return velocity;
* 5-minute and 15-minute relative-volume increase;
* volume acceleration before large 24-hour displacement;
* candle-range expansion after compression;
* repeated closes near candle highs for longs;
* repeated closes near candle lows for shorts;
* increasing directional efficiency;
* breakout proximity;
* declining pullback depth;
* VWAP or EMA reclaim;
* open-interest change where reliable data is available;
* taker-buy or taker-sell imbalance where reliable data is available;
* funding and basis as context, not standalone signals;
* low initial extension from the movement origin.

Potential early-gainer pattern:

```text
low or moderate 24h move
+ strong 5m/15m acceleration
+ rising relative volume
+ compression release
+ clean target space
+ price not yet terminally extended
```

Potential early-loser/short pattern:

```text
low or moderate 24h decline
+ breakdown acceleration
+ increasing sell participation
+ repeated failed reclaims
+ clean downside target space
```

The system must not create a separate gainer state machine. These are normal measurable market features used in opportunity scoring and strategy evaluation.

---

# 9. Detailed Multi-Timeframe Analysis

Run only on shortlisted symbols.

## 9.1 Default timeframes

| Timeframe | Primary role                            |
| --------- | --------------------------------------- |
| `1m`      | current impulse and precise execution   |
| `3m`      | microstructure and trigger confirmation |
| `5m`      | primary entry and stop structure        |
| `15m`     | setup structure and local trend         |
| `30m`     | intraday context and target space       |
| `1h`      | broader trend and major levels          |
| `4h`      | macro caution and major structure only  |

## 9.2 Timeframe rules

* `5m` and `15m` drive most normal intraday setups.
* `1m` and `3m` refine entry and immediate momentum.
* `30m` and `1h` refine confidence and targets.
* `4h` normally applies a warning or score adjustment.
* `4h` must not automatically veto a valid fast setup.
* No weekly or multi-day resampling is required in the default live scanner.

---

# 10. Feature Engine

The detailed feature engine should expose raw values rather than only boolean conclusions.

## 10.1 Trend and structure

* swing highs and swing lows;
* higher-high/higher-low sequences;
* lower-high/lower-low sequences;
* break of structure;
* change of character;
* local support and resistance;
* range boundaries;
* previous session or rolling highs/lows;
* distance to structural levels;
* trend slope;
* directional efficiency.

## 10.2 Momentum

* RSI level;
* RSI slope;
* RSI divergence where deterministic;
* MACD line, signal and histogram;
* MACD histogram acceleration;
* rate of change;
* candle-body direction persistence;
* close-location value;
* impulse strength;
* momentum decay.

RSI overbought does not automatically mean short.

RSI oversold does not automatically mean long.

Their interpretation depends on trend, structure, volume and momentum behavior.

## 10.3 Volume and participation

* raw volume;
* relative volume;
* volume moving average;
* volume acceleration;
* breakout volume;
* pullback volume contraction;
* directional volume approximation;
* taker imbalance where available;
* participation consistency.

## 10.4 Volatility

* ATR;
* ATR percentage;
* candle-range percentile;
* compression;
* expansion;
* wick-to-body ratio;
* noise ratio;
* stop feasibility;
* expected movement range.

## 10.5 Price location

* EMA distance;
* EMA ordering;
* VWAP distance;
* VWAP reclaim or rejection;
* range position;
* breakout distance;
* pullback depth;
* extension from impulse origin;
* target-space distance.

## 10.6 Futures context where reliably available

Potential contextual features:

* open interest;
* open-interest change;
* funding rate;
* long/short ratio;
* taker-buy/sell volume;
* liquidation activity;
* basis.

Missing futures-context data must never be fabricated.

Strategies must remain usable when optional data is unavailable.

---

# 11. Market-State Classification

Classification should be multi-label.

Possible active states:

* directional uptrend;
* directional downtrend;
* early bullish expansion;
* early bearish expansion;
* mature bullish expansion;
* mature bearish expansion;
* bullish pullback;
* bearish pullback;
* breakout attempt;
* confirmed breakout;
* breakdown attempt;
* confirmed breakdown;
* breakout retest;
* breakdown retest;
* volatility compression;
* stable range;
* range-edge rejection;
* failed bullish breakout;
* failed bearish breakdown;
* upside liquidity rejection;
* downside liquidity rejection;
* bullish exhaustion;
* bearish exhaustion;
* chaotic volatility;
* low-participation drift.

Example:

```text
early bullish expansion
+ breakout attempt
+ rising relative volume
+ moderate extension
```

Classification guides strategy applicability.

It does not issue a final trade decision by itself.

---

# 12. Strategy Engine

Every shortlisted symbol must be tested against every strategy applicable to its measured state.

A strategy returns one of:

```text
not_applicable
candidate
invalidated
```

`not_applicable` must not count as a rejection.

## 12.1 Core strategies

### 1. Momentum Breakout

Long:

* price approaches or breaks meaningful resistance;
* recent directional momentum strengthens;
* relative volume expands;
* closes remain strong;
* target space remains available;
* move is not terminally extended.

Short uses inverse logic.

### 2. Breakout Continuation

* initial break already occurred;
* price remains accepted outside the old structure;
* pullbacks stay shallow;
* momentum remains active;
* continuation space remains.

### 3. Breakout Retest

* meaningful level breaks;
* price retests the level;
* old resistance becomes support for long;
* old support becomes resistance for short;
* invalidation is structurally clear.

### 4. First Pullback Continuation

* clear initial expansion;
* first controlled retracement;
* pullback volume contracts;
* core structure remains intact;
* participation returns in the original direction.

### 5. Trend Pullback

* established directional structure;
* retracement into EMA, VWAP, prior breakout or local structure;
* momentum cools without trend failure;
* sufficient continuation space remains.

### 6. Compression Expansion

* recent volatility contracts;
* boundaries become identifiable;
* participation starts increasing;
* directional release begins or becomes imminent.

### 7. Range-Edge Reversal

* genuine range exists;
* price reaches a validated edge;
* rejection is measurable;
* enough space exists toward range midpoint or opposite edge.

### 8. Failed Breakout Reversal

* level is broken;
* continuation fails;
* price re-enters old structure;
* opposite-side momentum develops.

### 9. Liquidity-Rejection Reversal

* obvious high or low is swept;
* rejection closes back inside structure;
* follow-through supports reversal;
* stop can sit beyond the sweep extreme.

### 10. VWAP Reclaim or Rejection

* meaningful intraday VWAP interaction;
* participation confirms reclaim or rejection;
* local structure supports direction.

### 11. Momentum Scalp

* strong `1m–5m` acceleration;
* low spread;
* sufficient liquidity;
* immediate target space;
* short expected holding period.

### 12. Exhaustion Reversal

* extreme extension;
* momentum deterioration;
* rejection or failed continuation;
* structural failure begins.

This strategy must carry a larger uncertainty penalty.

---

# 13. Candidate Construction

A symbol can produce multiple candidates.

Example:

```text
SOLUSDT

1. LONG — first pullback continuation — 84
2. LONG — breakout retest — 78
3. SHORT — exhaustion reversal — 56
```

The scanner should:

* retain all candidates internally;
* select the highest-quality candidate as the primary symbol candidate;
* keep useful alternatives in JSON and verbose diagnostics;
* avoid displaying contradictory low-quality alternatives by default.

Each candidate must contain:

* symbol;
* direction;
* strategy;
* active market states;
* supporting evidence;
* contradicting evidence;
* entry geometry;
* invalidation;
* stop;
* target geometry;
* expected horizon;
* raw scores;
* final score;
* status;
* warnings.

---

# 14. Scoring Model

Remove `risk_feasibility_score`.

Required scores:

```text
opportunity_score
setup_score
timing_score
trade_quality_score
final_rank_score
```

## 14.1 Opportunity score

Market-wide movement and tradeability.

## 14.2 Setup score

How strongly the current structure matches the selected strategy.

Components:

* structure;
* momentum;
* volume;
* volatility suitability;
* target space;
* directional consistency;
* strategy-specific evidence;
* contradiction penalties.

## 14.3 Timing score

How usable the entry is now.

Components:

* distance from preferred entry;
* freshness;
* extension;
* recent trigger;
* chase risk;
* pullback availability;
* immediate continuation evidence.

## 14.4 Trade-quality score

Quality of the constructed plan itself.

Components:

* logical invalidation;
* structural stop quality;
* target clarity;
* stop distance versus expected movement;
* reward-to-risk geometry;
* spread and likely execution friction;
* expected horizon.

This is not wallet risk.

## 14.5 Final rank score

Suggested model:

```text
final_rank_score =
    opportunity_score × opportunity_weight
  + setup_score × setup_weight
  + timing_score × timing_weight
  + trade_quality_score × trade_quality_weight
  - warning_penalties
```

Suggested initial weights:

```yaml
opportunity: 0.25
setup: 0.40
timing: 0.20
trade_quality: 0.15
```

All weights configurable.

---

# 15. Entry Engine

The entry engine constructs a usable plan.

It is not another conservative rejection layer.

## 15.1 Required entry outputs

* current price;
* immediate entry zone;
* preferred entry zone;
* maximum chase price;
* trigger or maintenance condition;
* structural invalidation;
* stop-loss;
* stop distance percentage;
* TP1;
* TP2;
* TP3;
* reward-to-risk for each target;
* expected trade horizon;
* reasoning;
* caution.

## 15.2 Immediate and preferred entries

Where both are valid:

```text
Immediate entry:
Trade can be taken near current price with stated caution.

Preferred entry:
A nearby pullback or retest offers improved geometry.
```

The immediate entry must not be fabricated when price is clearly late.

## 15.3 Structural stop

Stop must derive from the strategy thesis:

* below pullback swing for long;
* above pullback swing for short;
* beyond breakout failure;
* beyond retest failure;
* beyond sweep extreme;
* beyond range invalidation;
* with volatility and execution buffer.

Stop must not be moved merely to produce an attractive reward-to-risk ratio.

---

# 16. Target and Trade-Management Engine

Every valid trade plan should return three target levels where structure permits.

## 16.1 TP1 — Initial realization

Purpose:

* capture the nearest realistic movement;
* reduce exposure if the setup starts working;
* often based on nearest liquidity or local structure.

## 16.2 TP2 — Primary objective

Purpose:

* represent the main expected move;
* use significant swing, range projection, ATR projection or opposing structure.

## 16.3 TP3 — Extended continuation

Purpose:

* capture exceptional continuation;
* only include when remaining structure and momentum support it.

## 16.4 TP follow-up guidance

Every plan should explain what to do if TP1 is reached.

Example continuation conditions:

```text
Hold toward TP2 while:
- price remains above the breakout level;
- 5m structure remains bullish;
- pullbacks remain shallow;
- volume does not collapse;
- no strong bearish rejection forms.
```

Example partial-exit conditions:

```text
Reduce or exit after TP1 if:
- price rejects the next resistance strongly;
- 1m and 3m momentum reverse together;
- 5m closes back below the reclaimed level;
- volume expands against the trade;
- a failed-breakout pattern develops.
```

## 16.5 Exit guidance

Every setup must include:

### Normal exit

* target-based exit;
* structural trailing condition;
* expected final objective.

### Early exit

* thesis weakening;
* failed continuation;
* opposite momentum;
* volume contradiction;
* reclaim/retest failure.

### Hard exit

* stop-loss;
* structural invalidation;
* decisive close beyond invalidation where strategy requires it.

### Time-based exit

For scalp and fast-intraday setups:

* define expected activation period;
* if price remains stagnant beyond the expected window, downgrade or exit;
* avoid holding a failed fast setup for several days.

---

# 17. Action Statuses

Use a small action-oriented set:

### `READY_NOW`

Price is inside or sufficiently close to the intended entry.

### `AGGRESSIVE_NOW`

Current entry is available but includes a meaningful caution.

### `PULLBACK_PREFERRED`

Immediate participation is possible, but a nearby pullback gives better geometry.

### `WATCH_NEAR_ENTRY`

Setup is valid and close, but the trigger or zone has not been reached.

### `LATE_OR_CHASING`

Direction may still be correct but current entry quality is poor.

### `INVALIDATED`

The strategy thesis has structurally failed.

Do not restore complicated reclaim/retest states as top-level statuses.

Reclaim and retest belong in:

* strategy;
* trigger;
* evidence;
* entry instructions.

---

# 18. Hard Rejection Rules

A candidate may be fully rejected only when:

* required market data is invalid;
* symbol is not an active eligible contract;
* liquidity or spread makes the market practically unusable;
* strategy conditions are absent;
* entry and invalidation are logically inconsistent;
* price has already crossed structural invalidation;
* no defensible stop can be constructed;
* no meaningful target space exists;
* setup is so late that positive trade geometry no longer exists.

Do not hard-reject solely because:

* one timeframe disagrees;
* RSI is overbought or oversold;
* a sweep may occur;
* entry is not perfect;
* wallet size is small;
* permitted loss is low;
* leverage would be high;
* the setup is aggressive;
* the candidate is lower confidence.

These should affect score, status or warnings where appropriate.

---

# 19. Scanner Result Policy

Broad scan should normally show `15–20` ranked candidates when enough usable markets exist.

However, result generation must not lower analytical standards merely to fill the count.

Recommended output grouping:

```text
Top actionable setups
Additional aggressive setups
Pullback or watch setups
```

Example:

```text
5 READY_NOW
4 AGGRESSIVE_NOW
5 PULLBACK_PREFERRED
3 WATCH_NEAR_ENTRY
```

Weak and invalidated candidates should not occupy the primary list merely to reach 20.

The scan summary should state:

```text
Eligible contracts
Screened contracts
Detailed symbols
Constructed candidates
Displayed candidates
Long candidates
Short candidates
Status counts
```

---

# 20. Default Trade Card

Each result should show:

```text
Rank
Symbol
Direction
Strategy
Status
Final score
Opportunity score
Setup score
Timing score
Trade-quality score

Current price
Immediate entry
Preferred entry
Maximum chase
Invalidation
Stop-loss
Stop distance

TP1
TP2
TP3
Reward-to-risk values
Expected horizon

Why long or short
Primary supporting evidence
Contradicting evidence
Main caution

TP1 follow-up
Continuation conditions
Early-exit conditions
Hard-exit condition
```

No wallet or leverage panel.

---

# 21. CLI Redesign

## 21.1 Active commands

Keep the public CLI intentionally small:

```bash
apex scan
apex analyze SYMBOL
apex config-check
apex backtest
apex version
```

`backtest` may remain only as a focused strategy-evaluation utility.

## 21.2 Broad scan

```bash
apex scan
```

Suggested options:

```text
--results 20
--shortlist 30
--direction long|short|both
--candles
--output text|json
--record
--config-dir
```

Remove:

```text
--wallet-balance
--risk-mode
--risk-per-trade
--leverage
--margin-mode
--profile
--paper
--gainer-mode
--scan-mode normal|gainers|all
```

## 21.3 Manual analysis

```bash
apex analyze BTCUSDT
```

Suggested options:

```text
--output text|json
--candles
--record
--config-dir
```

## 21.4 Command cleanup

Unregister or remove active command groups for:

* paper operations;
* funded history;
* validation review;
* readiness;
* intelligence placeholders;
* execution;
* kill switches;
* dataset campaigns;
* forward-edge campaigns;
* milestone reviews;
* historical orchestration;
* automatic optimization.

Any retained internal developer command must not appear in standard user help.

---

# 22. Configuration Redesign

Use four focused configuration files:

```text
config/
├── market.yaml
├── strategies.yaml
├── scoring.yaml
└── runtime.yaml
```

## 22.1 `market.yaml`

Contains:

* Binance futures provider;
* quote asset;
* perpetual-only rule;
* spread eligibility;
* minimum liquidity;
* history requirements;
* timeframes;
* screener candle sample;
* shortlist size;
* displayed-result count;
* blacklist;
* optional allowlist.

## 22.2 `strategies.yaml`

Contains:

* enabled strategies;
* applicability thresholds;
* strategy-specific parameters;
* stop buffers;
* target construction settings;
* expected horizons.

## 22.3 `scoring.yaml`

Contains:

* opportunity weights;
* setup weights;
* timing weights;
* trade-quality weights;
* warning penalties;
* status boundaries;
* final ranking weights.

## 22.4 `runtime.yaml`

Contains:

* request timeouts;
* retries;
* concurrency;
* Binance rate-limit handling;
* cache duration;
* output defaults;
* logging paths;
* data directories.

Remove active `risk.yaml` from Stage 3.

Preserve it only in an archive if older code temporarily needs migration support.

---

# 23. Logging and Manual Improvement Loop

Every broad scan must write enough information to reconstruct its decision.

## 23.1 Scan record

Store:

* timestamp;
* eligible universe;
* excluded symbols and exact reasons;
* ticker snapshot;
* lightweight screening features;
* opportunity scores;
* shortlist;
* detailed timeframe features;
* market states;
* every applicable strategy result;
* all generated candidates;
* evidence and contradictions;
* entry geometry;
* targets;
* status;
* every score component;
* final ranking;
* configuration hash.

## 23.2 Later outcome comparison

A separate evaluator may later append:

* whether immediate entry was reached;
* whether preferred entry was reached;
* maximum favorable excursion;
* maximum adverse excursion;
* TP1/TP2/TP3 hits;
* stop hit;
* time to target;
* time to invalidation;
* best achieved reward multiple;
* outcome by strategy;
* outcome by score band;
* outcome by market state.

## 23.3 No autonomous mutation

The program must not automatically:

* change thresholds;
* promote strategies;
* rewrite YAML;
* replace baseline parameters;
* learn from a single trade;
* optimize live behavior without explicit review.

Logs are inspected manually and changes are implemented deliberately in code or configuration.

---

# 24. Repository Cleanup Strategy

Bulk cleanup must be aggressive but dependency-aware.

Do not blindly delete files first.

## 24.1 Inventory before deletion

Build exact repository-wide reference inventories for:

* risk profiles;
* wallet inputs;
* leverage planning;
* funded account code;
* gainer concepts;
* spot CLI;
* paper trading;
* paper schedulers;
* execution and kill switches;
* optimization;
* readiness and validation;
* dataset campaigns;
* milestone terminology;
* output overlays;
* old serialized schemas;
* tests importing removed modules.

## 24.2 Preserve trade-finding foundations

Do not delete useful components for:

* Binance market-data providers;
* candle normalization;
* ticker handling;
* exchange metadata;
* feature calculations;
* indicators;
* swing and structure detection;
* liquidity sweeps;
* volatility;
* strategy calculations;
* entry geometry;
* structural stops;
* targets;
* scoring primitives;
* deterministic serialization;
* chronological simulation;
* scan logging.

## 24.3 Remove from active source

After reference migration:

* wallet-aware analysis coupling;
* risk profiles;
* leverage selectors;
* margin-mode models;
* funded-account planners;
* gainer models and routing;
* duplicated spot/futures presentation;
* paper operational workflows;
* testnet execution;
* autonomous optimization orchestration;
* readiness and review ceremony;
* obsolete CLI overlays;
* campaign-specific commands;
* dead compatibility facades;
* roadmap-era classes and fields.

## 24.4 Temporary archive rule

Archive only when code may still help near-term manual research.

Anything archived must:

* not be imported by production scanning;
* not register CLI commands;
* not appear in README;
* not affect configuration loading;
* not be required by normal tests.

Permanent dead code should be deleted rather than indefinitely archived.

---

# 25. Implementation Sequence

This is one redesign program, but it should be implemented in controlled batches so failures can be isolated.

## Batch 1 — Lock and inventory

* capture current Git commit;
* capture complete CLI help;
* list active configs;
* list public contracts and serialized fields;
* record test count;
* map imports and dependencies;
* locate every risk, wallet, funded, leverage, paper, gainer, spot, execution and campaign reference;
* identify core trade-finding modules to retain.

No deletion yet.

## Batch 2 — Define new contracts

Create clean contracts for:

* eligible contract;
* screener feature snapshot;
* opportunity score;
* market states;
* strategy evaluation;
* trade candidate;
* entry plan;
* target plan;
* exit guidance;
* trade status;
* ranked opportunity;
* scan result.

No wallet or risk-profile fields.

Add contract tests before migrating behavior.

## Batch 3 — Replace CLI surface

* rebuild CLI registration;
* expose only intended active commands;
* remove command overlays;
* remove paper sub-app registration;
* remove campaign and validation registrations;
* simplify help;
* keep text and JSON outputs.

At this point old internal modules may still exist but must be unreachable from the public CLI.

## Batch 4 — Remove risk coupling

* stop loading risk configuration in `scan` and `analyze`;
* remove risk arguments from application services;
* remove risk-based candidate rejection;
* remove risk feasibility from scoring;
* remove wallet/leverage output;
* update serializers, formatters and tests.

## Batch 5 — Dynamic universe

* implement Binance USDT perpetual discovery;
* cache exchange metadata;
* normalize symbols;
* apply eligibility and blacklist rules;
* test inactive and malformed contracts;
* retain manual symbol override for `analyze`.

## Batch 6 — Lightweight broad screener

* batch ticker retrieval;
* fetch limited recent candles;
* calculate lightweight features;
* calculate opportunity score;
* shortlist top 30;
* log component scores;
* verify each symbol appears once.

## Batch 7 — Detailed feature pipeline

* unify multi-timeframe feature extraction;
* establish timeframe roles;
* expose raw indicator values;
* add market-state classifier;
* prevent 4h context from becoming an automatic veto.

## Batch 8 — Strategy engine

* migrate useful existing strategies;
* remove mode-based routing;
* add applicability evaluation;
* evaluate relevant long and short strategies;
* retain alternative candidates;
* log positive and negative evidence.

## Batch 9 — Entry and trade management

* simplify statuses;
* generate immediate and preferred entries;
* add chase boundary;
* derive structural invalidation and stop;
* build three targets;
* add reward-to-risk geometry;
* add TP follow-up and early-exit logic;
* add time-based invalidation.

## Batch 10 — Ranking and scanner output

* calculate the four new score groups;
* rank across all candidate symbols;
* display top 15–20;
* group actionable and developing setups;
* add concise text cards;
* provide complete JSON diagnostics.

## Batch 11 — Logging and evaluator

* create structured scan records;
* preserve configuration version;
* create optional manual outcome-evaluation utilities;
* remove automatic threshold mutation and promotion.

## Batch 12 — Delete obsolete systems

After imports are clean:

* delete dead risk modules;
* delete funded modules;
* delete gainer modules;
* delete paper operational modules;
* delete execution modules;
* delete unused CLI command modules;
* delete dead configs;
* delete obsolete tests;
* delete compatibility layers no longer needed.

## Batch 13 — Documentation and terminology

* rewrite README for trade discovery only;
* create Stage 3 architecture documentation;
* remove development-stage and milestone terminology;
* document scoring and limitations;
* document Binance data dependencies;
* document scan and analyze commands;
* remove wallet, funded, paper and execution claims.

## Batch 14 — Full validation

Run repository-wide:

```bash
cd ~/data_drive/apex
git pull --rebase origin main
source .venv/bin/activate

.venv/bin/ruff format src tests
.venv/bin/ruff check src tests --fix
.venv/bin/ruff check src tests
.venv/bin/mypy src
.venv/bin/pytest
git diff --check
```

No test result may be claimed until actual terminal output is provided.

---

# 26. Required Test Coverage

## Universe tests

* only active USDT perpetual contracts selected;
* inactive contracts excluded;
* duplicate symbols eliminated;
* blacklists respected;
* malformed metadata handled.

## Screener tests

* opportunity score deterministic;
* acceleration recognized;
* early expansion ranks above stale expansion;
* excessive spread penalized;
* chaotic noise penalized;
* shortlist count enforced;
* long and short opportunities remain eligible.

## Strategy tests

For every strategy:

* long positive example;
* short positive example;
* not-applicable example;
* invalidated example;
* missing optional data example;
* contradictory evidence example.

## Entry tests

* current price inside entry;
* immediate versus preferred entry;
* long and short stop geometry;
* chase boundary;
* invalidated setup;
* pullback preferred;
* target ordering;
* reward-to-risk calculations;
* TP follow-up guidance.

## Ranking tests

* higher setup quality outranks wallet-independent weak candidates;
* stale high-volume move does not automatically beat fresh expansion;
* risk profile has no influence because none exists;
* lower-timeframe valid setup survives 4h disagreement with penalty;
* deterministic ordering for equal scores.

## CLI tests

* only intended commands visible;
* `scan` requires no wallet;
* `analyze` requires no wallet;
* removed paper and execution commands unavailable;
* text output excludes risk profile;
* JSON output excludes wallet and leverage fields.

---

# 27. Acceptance Criteria

Stage 3 is complete only when:

## Product surface

* public CLI contains only the simplified active commands;
* broad scan and manual analysis are the two active discovery modes;
* no active spot workflow exists;
* no active paper or execution workflow exists.

## Discovery

* scanner dynamically discovers active Binance USDT perpetual futures;
* all eligible contracts are screened;
* each symbol is screened once;
* approximately 30 symbols receive detailed analysis by default;
* top 15–20 candidates are displayed when enough valid candidates exist.

## Analysis

* long and short strategies are evaluated;
* multiple strategy candidates can exist per symbol;
* market states are measurable and multi-label;
* early expansion can be detected before a coin becomes an obvious top gainer;
* 4h context normally adjusts score rather than vetoing a fast setup.

## Trade plans

Every usable primary candidate includes:

* direction;
* strategy;
* reasons;
* current price;
* immediate entry;
* preferred entry where available;
* maximum chase;
* invalidation;
* structural stop;
* TP1, TP2 and TP3;
* reward-to-risk;
* expected horizon;
* TP follow-up;
* continuation conditions;
* early-exit conditions;
* hard-exit condition;
* cautions.

## Removal

No active scan or analysis contains:

* wallet balance;
* risk profile;
* maximum planned loss;
* margin mode;
* leverage mode;
* funded rules;
* position sizing;
* liquidation calculations;
* gainer mode;
* paper approval;
* execution readiness.

## Transparency

* every score is decomposable;
* every candidate includes positive and contradictory evidence;
* every exclusion has a reason;
* every scan is reproducible from its logged configuration and inputs;
* no unavailable market data is invented.

## Quality

* Ruff passes;
* strict mypy passes;
* relevant and full pytest suites pass;
* `git diff --check` passes;
* actual outputs are supplied before validation is declared successful.

---

# 28. Intended Final Experience

## Broad scan

```bash
apex scan
```

Expected workflow:

```text
Apex loads all active Binance USDT perpetual contracts.

It removes only genuinely unusable markets.

It screens the complete market for liquidity, movement,
acceleration, volume, volatility, freshness and structure.

It performs detailed analysis on approximately 30 shortlisted symbols.

It evaluates applicable long and short strategies.

It ranks and displays approximately 15–20 best available candidates.
```

## Manual analysis

```bash
apex analyze SOLUSDT
```

Expected result:

```text
Primary direction and strategy
Alternative strategy candidates
Why long or short
Current and preferred entries
Maximum chase
Structural invalidation
Stop-loss
TP1, TP2 and TP3
Expected trade horizon
TP1 hold or exit guidance
Momentum-failure exit conditions
Supporting and contradicting evidence
Transparent component scores
```

The final Stage 3 Apex product is:

> A focused Binance futures trade-discovery and trade-planning engine. It finds, explains and ranks actionable opportunities. It does not manage the wallet, choose leverage, operate a funded account, execute orders or hide market setups behind unrelated risk-profile gates.
