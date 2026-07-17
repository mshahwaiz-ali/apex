# Apex Trade Analysis Methodology Upgrade

## 1. Purpose

This document defines the methodology for improving Apex trade discovery and post-shortlist coin analysis.

Apex is already an operational deterministic Binance USDT perpetual-futures analysis system. This work must not redesign the repository, replace the CLI, or create a separate analysis engine.

The objective is to improve the quality of results returned by:

```text
apex scan
apex analyze SYMBOL
```

Both commands must use the same shared trade-analysis core.

The only intended difference is:

* `apex scan` selects and shortlists symbols before analysis.
* `apex analyze SYMBOL` analyzes the requested symbol directly.

After symbol selection, both commands must apply identical:

* market-state classification;
* strategy routing;
* setup detection;
* entry construction;
* stop-loss placement;
* target projection;
* setup expiry;
* scoring;
* rejection rules;
* reasoning;
* and output wording.

---

# 2. Core Objective

Apex should find the strongest currently available long and short opportunities without forcing trades.

The engine must answer these questions in order:

1. Is this coin currently tradable?
2. What market state is it in?
3. Which strategies are valid for this state?
4. Is a real setup present?
5. Has the setup completed or is it still developing?
6. Is an entry available near current market price?
7. Is a superior entry likely on a nearby retest or pullback?
8. Is a farther future entry worth monitoring?
9. Where is the structural invalidation?
10. What movement can the structure reasonably support?
11. What are the realistic target levels?
12. How long may the setup and trade remain valid?
13. Does the reward justify the risk and execution cost?
14. Why was the trade selected, downgraded, deferred, or rejected?

The engine must not start with:

> “Which indicators are bullish?”

It must start with:

> “What is this market currently doing?”

---

# 3. Methodology Sources

The methodology combines three distinct roles.

## 3.1 John J. Murphy — Market Structure

Murphy supplies the primary framework for:

* trend classification;
* swing structure;
* support and resistance;
* polarity changes;
* breakouts;
* failed breakouts;
* trendlines;
* channels;
* pattern completion;
* structural confirmation;
* multi-timeframe context;
* measured targets;
* and structural invalidation.

Main implementation principle:

> Structure determines the setup. Indicators only provide supporting evidence.

Murphy also establishes that analysis and entry timing are separate decisions. A bullish market bias does not automatically mean that a long entry is currently available.

## 3.2 Steve Nison — Candle Evidence and Timing

Nison supplies:

* candle anatomy;
* rejection evidence;
* reversal warnings;
* candle completion rules;
* contextual candle interpretation;
* lower-timeframe trigger refinement;
* and candle-based timing assistance.

Candlesticks must not become the primary strategy router.

A candle pattern may:

* strengthen an existing setup;
* weaken it;
* provide an entry trigger;
* warn that momentum is failing;
* or support an exit.

It must not independently bypass:

* regime compatibility;
* structural context;
* liquidity;
* stop validity;
* reward-to-risk;
* or target feasibility.

Candlestick patterns normally do not provide price targets. Targets must come from structure.

## 3.3 Mark Douglas — Process and Probabilistic Discipline

Douglas supplies the operating rules around the methodology:

* no individual trade is certain;
* an edge exists over a sample, not one outcome;
* pattern detection is different from trade approval;
* risk must be defined before approval;
* recent wins and losses must not alter deterministic decisions;
* confidence must describe evidence quality rather than emotional certainty;
* and output wording must never imply a guaranteed result.

`READY_NOW` must mean:

> All execution conditions are currently complete.

It must not mean:

> This trade is highly likely to win.

---

# 4. Required Analysis Architecture

The upgraded analysis should use the following ordered pipeline:

```text
Market usability
→ Market-state classification
→ Multi-timeframe structural map
→ Strategy eligibility
→ Setup detection
→ Setup maturity
→ Entry opportunity search
→ Structural invalidation
→ Target projection
→ Time and expiry estimation
→ Trade-quality scoring
→ Hard rejection rules
→ Candidate ranking
→ Reasoned output
```

No later stage should compensate for failure in an earlier stage.

Examples:

* A strong candle cannot fix an invalid market regime.
* High relative volume cannot fix a late entry.
* A distant target cannot fix poor reward before the first obstacle.
* A high momentum score cannot fix an invalid stop.
* Ten confirming indicators cannot make a structurally incomplete setup executable.

---

# 5. Market Usability Gate

Before strategy analysis, Apex should determine whether the market can support reliable execution.

## Required checks

* sufficient quote volume;
* acceptable spread;
* acceptable candle continuity;
* sufficient price history;
* usable volatility;
* no extreme noise;
* no abnormal stale data;
* sufficient order-book or ticker quality where available;
* contract precision compatibility;
* no blacklist restriction.

## Output

```text
USABLE
USABLE_WITH_CAUTION
UNUSABLE
DATA_INCOMPLETE
```

A symbol that fails this layer may still be shown as rejected, but it must not continue to trade approval.

---

# 6. Market-State Classification

Apex should classify the coin before selecting a strategy.

A coin may be in one primary state and several secondary conditions.

## Primary states

```text
TRENDING_UP
TRENDING_DOWN
RANGING
COMPRESSING
BREAKOUT_ATTEMPT
BREAKDOWN_ATTEMPT
POST_BREAKOUT
POST_BREAKDOWN
PULLBACK_IN_UPTREND
RALLY_IN_DOWNTREND
REVERSAL_ATTEMPT_UP
REVERSAL_ATTEMPT_DOWN
EXHAUSTED_UP
EXHAUSTED_DOWN
CHAOTIC
TRANSITIONAL
```

## Secondary conditions

```text
LOW_LIQUIDITY
HIGH_VOLATILITY
VOLATILITY_EXPANSION
VOLATILITY_CONTRACTION
VOLUME_EXPANSION
VOLUME_DIVERGENCE
OVEREXTENDED
NEAR_MAJOR_SUPPORT
NEAR_MAJOR_RESISTANCE
LIQUIDITY_SWEEP
FAILED_BREAKOUT
FAILED_BREAKDOWN
HTF_CONFLICT
```

## Classification inputs

The classifier should prioritize independent evidence families:

### Structure

* higher highs and higher lows;
* lower highs and lower lows;
* structural breaks;
* swing amplitude;
* trend age;
* range boundaries;
* channel position;
* support/resistance proximity.

### Volatility

* ATR percentage;
* range expansion;
* range compression;
* realized movement distribution;
* volatility percentile.

### Participation

* relative volume;
* impulse-versus-pullback volume;
* volume acceleration;
* breakout participation;
* retest volume contraction;
* open interest and taker flow when reliably available.

### Price location

* location inside the current range;
* distance from recent high or low;
* distance from structural levels;
* VWAP relationship;
* extension from trend mean;
* remaining room before the next obstacle.

Indicators must not be counted as independent evidence when they measure substantially the same phenomenon.

For example:

* RSI and stochastic largely represent momentum;
* several EMAs largely represent trend;
* ATR and candle range both describe volatility.

They may refine analysis but must not create artificial confluence.

---

# 7. Strategy Routing

Apex must not run every strategy equally on every symbol.

The market-state classifier should produce an eligible strategy set.

## Example routing

| Market state                   | Primary eligible strategies                                            |
| ------------------------------ | ---------------------------------------------------------------------- |
| Established uptrend            | Trend pullback, first-pullback continuation, breakout continuation     |
| Established downtrend          | Short trend pullback, first-rally continuation, breakdown continuation |
| Clean range                    | Range reversal at boundaries                                           |
| Compression                    | Compression expansion watch                                            |
| Confirmed breakout             | Breakout continuation or breakout retest                               |
| Failed breakout                | Failed-breakout reversal                                               |
| Liquidity sweep at structure   | Liquidity-rejection reversal                                           |
| Trend exhaustion               | Exhaustion warning; reversal only after confirmation                   |
| Chaotic/noisy structure        | No trade                                                               |
| Weak undefined sideways market | No trade                                                               |

Each strategy must declare:

* compatible market states;
* prohibited market states;
* required prior structure;
* setup timeframe;
* trigger timeframe;
* confirmation basis;
* structural invalidation method;
* target methods;
* expiry policy;
* required evidence;
* optional evidence;
* rejection conditions.

---

# 8. Strategy Candidate Contract

Every strategy candidate should return a common normalized contract.

```text
strategy_id
strategy_version
direction
market_state
market_bias
setup_timeframe
trigger_timeframe
risk_timeframe
target_timeframe
setup_detected
setup_completed
confirmation_basis
confirmation_status
entry_state
entry_zones
ideal_entry
maximum_chase
invalidation_level
stop_price
target_candidates
selected_targets
expected_hold
setup_expiry
evidence
contradictions
warnings
rejection_reasons
scores
```

Strategies should generate candidates. They should not make the final global ranking decision themselves.

---

# 9. Setup Maturity

Pattern presence is not enough.

Apex must distinguish:

```text
PATTERN_DEVELOPING
TRIGGER_PROVISIONAL
CONFIRMATION_PENDING_CLOSE
SETUP_CONFIRMED
RETEST_PENDING
ENTRY_AVAILABLE
ENTRY_MISSED
PATTERN_FAILED
INVALIDATED
```

Active-candle information may be used for:

* monitoring;
* early warning;
* approaching-entry status;
* provisional trigger detection.

When the strategy requires a close, the active candle must not become final confirmation.

---

# 10. Entry Opportunity Search

Apex should search for more than one entry possibility.

For every valid setup, it should evaluate three entry classes.

## 10.1 Immediate entry

A valid entry at or close to current market price.

Requirements:

* completed trigger;
* acceptable current geometry;
* price not beyond maximum chase;
* valid stop;
* sufficient room before the first obstacle;
* acceptable expected reward after costs.

## 10.2 Preferred nearby entry

A nearby pullback, retest, reclaim, or rejection zone that improves geometry.

This should include:

* zone low and high;
* ideal entry;
* required confirmation;
* estimated distance from current price;
* invalidation;
* maximum waiting distance or bars;
* reason it is superior to immediate entry.

A preferred entry must not automatically suppress a still-valid immediate entry. Apex may report both:

```text
Immediate entry is valid.
Preferred retracement offers better geometry.
```

## 10.3 Developing future entry

A setup that is not currently actionable but may become valid at a meaningful nearby level.

Examples:

* breakout level not yet reached;
* retest expected after a confirmed breakout;
* pullback toward structural support;
* reclaim required after a sweep;
* range-boundary test;
* trendline reaction;
* confirmation above or below a trigger level.

The engine should report it only when:

* the setup has identifiable structure;
* the entry condition is objective;
* invalidation is already definable;
* and the distance is not so large that the forecast becomes speculative.

## Entry zone fields

```text
zone_low
zone_high
ideal_entry
confirmation_level
maximum_chase
current_distance_percentage
current_distance_atr
entry_type
entry_reason
```

Entry zones must be structural ranges, not arbitrary single prices.

---

# 11. Entry Status Model

Recommended execution statuses:

```text
READY_NOW
AGGRESSIVE_NOW
PREFERRED_ENTRY_NEARBY
APPROACHING_ENTRY
WAIT_FOR_CLOSE
WAIT_FOR_RETEST
WAIT_FOR_RECLAIM
DEVELOPING_SETUP
LATE_OR_CHASING
MISSED_ENTRY
INVALIDATED
NO_TRADE
```

## Meaning of `READY_NOW`

`READY_NOW` requires:

* valid market;
* compatible regime;
* completed setup;
* completed trigger;
* acceptable entry location;
* valid stop;
* acceptable target room;
* no hard rejection;
* current price inside or immediately adjacent to the permitted entry zone.

It does not communicate a guaranteed or high-probability outcome.

---

# 12. Stop-Loss Methodology

Stops must come from the level that disproves the setup.

## Stop hierarchy

1. Pattern invalidation
2. Swing invalidation
3. Structural-zone invalidation
4. Volatility buffer
5. Tick-size and round-number adjustment
6. Execution-cost allowance

## Prohibited stop construction

* arbitrary fixed percentage;
* stop selected merely to improve displayed R:R;
* stop inside the entry zone;
* stop on the wrong side of structure;
* stop exactly at an obvious round number without justification;
* stop based only on leverage or desired monetary loss;
* widening a stop after entry without new confirmed structure.

## Required stop reasoning

Apex should explain:

```text
Stop is below the confirmed swing low and support zone.
A volatility buffer of X ATR is applied.
A close below this level invalidates the pullback-continuation thesis.
```

The signal-analysis layer should define price risk. Account position sizing, leverage and liquidation should remain separate unless Apex explicitly restores those product capabilities.

---

# 13. Target Projection

Apex must not force every trade toward 10%.

A 3% structurally supported move can be superior to a theoretical 10% move blocked by nearby resistance.

Likewise, a 10% or larger objective is valid when the market structure, volatility, pattern dimensions and higher-timeframe room support it.

## Target sources

Targets should be generated from:

1. nearest structural obstacle;
2. prior swing high or low;
3. opposing range boundary;
4. breakout or breakdown measured move;
5. channel width;
6. pattern objective;
7. higher-timeframe support or resistance;
8. volatility-supported extension;
9. optional runner extension.

## Target roles

```text
TP1 = first realistic obstacle or risk-reduction level
TP2 = primary structural objective
TP3 = extended objective when continuation remains valid
RUNNER = conditional target, not assumed
```

## Target validation

For each target calculate:

* distance from expected fill;
* gross percentage movement;
* expected R multiple;
* obstacle quality;
* historical volatility feasibility;
* timeframe compatibility;
* estimated time requirement;
* probability category only when empirically calibrated;
* reason and source.

## Target rejection

Reject or downgrade a setup when:

* the first obstacle produces unacceptable R:R;
* the target is based only on a fixed percentage;
* expected movement exceeds realistic volatility without a catalyst state;
* the target requires passing several major structural barriers;
* target projection comes from leverage return rather than price movement.

---

# 14. Expected Movement Range

Instead of predicting one exact target, Apex should estimate a movement envelope.

```text
minimum_expected_move
primary_expected_move
extended_move
historical_volatility_range
structural_max_before_major_obstacle
```

Example:

```text
Minimum supported movement: 2.4%
Primary structural objective: 4.8%
Extended target: 8.1%
10%+ requires acceptance above the higher-timeframe resistance.
```

This provides useful upside information without pretending the furthest target is equally achievable.

---

# 15. Trade Duration and Setup Expiry

Holding duration must not be hardcoded as “quick trade.”

Expected holding time should be derived from:

* setup timeframe;
* trigger timeframe;
* pattern width and duration;
* ATR and realized volatility;
* distance to target;
* trend state;
* expected retest behavior;
* historical time-to-target for comparable setups.

## Output

```text
expected_hold_min
expected_hold_max
expected_bars
expiry_bars
expiry_reason
```

Example categories:

```text
MICRO_SCALP
SCALP
INTRADAY
MULTI_SESSION
SWING
```

The label must follow the structure. It must not determine the structure.

## Expiry examples

* breakout candidate expires after acceptance back inside the range;
* retest candidate expires when price travels beyond maximum chase without retesting;
* pullback candidate expires when the trend structure breaks;
* reversal candidate expires when the original trend resumes;
* setup expires when required confirmation does not occur within its empirically defined bar window.

---

# 16. Scoring Model

A single blended confidence score is insufficient.

Apex should expose separate dimensions.

## Recommended scores

```text
market_quality_score
regime_fit_score
structure_quality_score
setup_completeness_score
confirmation_quality_score
entry_quality_score
risk_quality_score
target_quality_score
timeframe_alignment_score
participation_score
data_quality_score
historical_edge_score
overall_trade_quality_score
```

## Scoring rules

* Scores represent analytical quality, not certainty.
* Missing mandatory evidence cannot be compensated by optional evidence.
* Hard rejection conditions override scores.
* Correlated evidence cannot be counted repeatedly.
* Historical edge score requires relevant out-of-sample data.
* No score should be presented as win probability unless calibrated.

## Suggested ranking priority

1. Hard eligibility
2. Regime compatibility
3. Setup completeness
4. Entry freshness
5. Structural stop validity
6. Reward before first obstacle
7. Target feasibility
8. Multi-timeframe alignment
9. Participation confirmation
10. Historical calibration
11. Data quality

---

# 17. Hard Rejection Rules

A candidate must be rejected when any mandatory rule fails.

Examples:

```text
UNUSABLE_MARKET
INSUFFICIENT_DATA
WRONG_REGIME
NO_PRIOR_TREND
SETUP_INCOMPLETE
ACTIVE_CANDLE_UNCONFIRMED
ENTRY_CHASED
ENTRY_MISSED
INVALID_STOP_GEOMETRY
INSUFFICIENT_TARGET_ROOM
POOR_REWARD_TO_RISK
MAJOR_HTF_CONFLICT
EXCESSIVE_NOISE
PATTERN_FAILED
STALE_DATA
```

The reason must identify the failed rule and observed value.

Weak candidates should not be returned merely to fill the requested result count.

---

# 18. Candidate Ranking

The scanner should rank opportunities after complete analysis, not only by initial screening momentum.

Two rankings are required.

## 18.1 Discovery rank

Used to decide which symbols receive expensive analysis.

Inputs may include:

* liquidity;
* movement;
* acceleration;
* relative volume;
* usable volatility;
* spread;
* structure proximity;
* directional clarity;
* freshness.

## 18.2 Trade rank

Used after full strategy analysis.

Inputs should include:

* valid strategy fit;
* setup maturity;
* entry quality;
* structural risk;
* target feasibility;
* first-obstacle R:R;
* timeframe alignment;
* participation;
* historical calibration;
* data quality.

A coin can have a high discovery rank but no valid trade.

A quieter coin can have a lower discovery rank but superior trade geometry.

---

# 19. Coin-Specific Strategy Adaptation

Apex should not create a manually customized strategy for every coin.

Instead, it should create deterministic symbol-behavior profiles from historical data.

Potential profile fields:

```text
normal_atr_percentage_by_timeframe
normal_spread
normal_volume
impulse_distribution
pullback_depth_distribution
breakout_follow_through_rate
retest_frequency
failed_breakout_rate
average_favorable_excursion
average_adverse_excursion
median_time_to_tp
median_time_to_invalidation
trend_persistence
range_frequency
wick_behavior
gap_or_discontinuity_frequency
```

These profiles can adapt thresholds without altering strategy definitions.

Examples:

* A volatile altcoin may require wider ATR-normalized zones.
* A liquid major may allow tighter confirmation thresholds.
* A coin with frequent false breakouts may require retest confirmation.
* A coin with strong continuation statistics may permit confirmed-close entry.
* A mean-reverting coin may route more frequently toward range strategies.

All adaptations must be:

* versioned;
* reproducible;
* learned only from past data;
* protected against look-ahead leakage;
* validated on unseen periods.

---

# 20. Evidence and Reasoning Output

Every selected setup should explain:

## Why this coin

* discovery reason;
* liquidity;
* movement;
* volatility;
* market-state opportunity.

## Why this direction

* higher-timeframe structure;
* setup-timeframe structure;
* directional evidence;
* opposing evidence.

## Why this strategy

* compatible regime;
* exact setup conditions;
* completed trigger;
* reasons alternative strategies were not selected.

## Why this entry

* zone construction;
* current-price relationship;
* preferred entry;
* maximum chase;
* confirmation rule.

## Why this stop

* structural invalidation;
* buffer;
* exact failure condition.

## Why these targets

* structural source of every target;
* expected percentage move;
* R multiple;
* obstacles;
* extension conditions.

## Why this duration

* setup timeframe;
* target distance;
* volatility;
* comparable historical behavior.

## Why this score

* component scores;
* major strengths;
* contradictions;
* uncertainty;
* missing data.

---

# 21. Example Result

```text
Symbol: XYZUSDT
Direction: LONG
Strategy: Breakout Retest
Status: PREFERRED_ENTRY_NEARBY

Market state:
Confirmed 15m range breakout inside a 1h uptrend.

Current price:
1.245

Immediate entry:
1.238–1.247
Valid but near the upper edge of acceptable geometry.

Preferred entry:
1.212–1.226
Retest of prior resistance turned support.

Ideal entry:
1.219

Maximum chase:
1.252

Invalidation:
15m close below 1.188.

Stop:
1.181, below the retest zone and confirmed swing low with volatility buffer.

Targets:
TP1 1.274 — nearest structural resistance, +4.5%
TP2 1.315 — range measured objective, +7.9%
TP3 1.354 — higher-timeframe extension, +11.1%

Expected holding time:
6–24 hours based on 15m setup width, ATR and target distance.

Primary reasons:
- 1h trend aligned upward.
- 15m breakout closed beyond resistance.
- Pullback volume is contracting.
- Retest zone remains structurally valid.
- First target provides acceptable reward before resistance.

Main risks:
- Current price is above ideal entry.
- TP3 requires acceptance above TP2 resistance.
- Outcome remains uncertain despite valid setup.
```

---

# 22. Validation Requirements

No methodology change should be considered complete without chronological testing.

Required testing:

* closed-candle replay;
* no future leakage;
* realistic entry-touch rules;
* same-candle stop/target ambiguity handled conservatively;
* fees and slippage;
* missed entries;
* setup expiry;
* partial targets;
* strategy-specific results;
* market-state-specific results;
* long and short separation;
* symbol-profile validation;
* train/validation/test separation.

Required metrics:

```text
sample_size
win_rate
expectancy
profit_factor
maximum_drawdown
average_R
median_R
MAE
MFE
time_to_entry
time_to_target
time_to_stop
missed_entry_rate
expiry_rate
strategy_distribution
regime_distribution
long_short_distribution
```

The main optimization objective should not be win rate alone.

Prefer:

* positive expectancy;
* stable profit factor;
* controlled drawdown;
* reasonable sample size;
* performance stability across symbols and regimes;
* realistic execution;
* no dependence on one exceptional trade.

---

# 23. Codex Implementation Sequence

## Phase 1 — Current Pipeline Audit

Map exact code paths for:

```text
scan
analyze
screening
shortlisting
feature calculation
market environment
strategy routing
candidate generation
entry geometry
stop calculation
target calculation
scoring
ranking
presentation
backtesting
```

Document duplicated logic and verify whether `scan` and `analyze` already converge on one analysis service.

No behavior change in this phase.

## Phase 2 — Shared Analysis Contract

Create or refine normalized contracts for:

* market state;
* strategy candidate;
* entry opportunity;
* structural invalidation;
* target candidate;
* evidence item;
* contradiction;
* rejection reason;
* score components;
* expected duration.

Preserve existing external CLI compatibility where practical.

## Phase 3 — Market-State Classifier

Implement deterministic primary and secondary market-state classification.

Add tests using synthetic and historical candle fixtures.

## Phase 4 — Strategy Eligibility Matrix

Move strategies from globally competing candidates toward explicit state-based routing.

Every strategy must declare applicability and prohibition rules.

## Phase 5 — Entry Search Engine

Support:

* immediate entry;
* preferred nearby entry;
* developing future entry;
* structural zones;
* ideal price;
* maximum chase;
* close/retest/reclaim triggers;
* missed-entry handling.

## Phase 6 — Stop and Invalidation Engine

Separate:

* thesis invalidation;
* stop price;
* volatility buffer;
* execution warning.

Ensure stops cannot be altered merely to improve R:R.

## Phase 7 — Structural Target Engine

Generate and rank targets from structural sources.

Add movement envelopes and conditional 10%+ extensions.

## Phase 8 — Duration and Expiry

Derive setup expiry and expected holding period from timeframe, volatility, structure and historical behavior.

## Phase 9 — Multidimensional Scoring

Replace misleading blended confidence with component scores and hard gates.

Avoid double-counting correlated indicators.

## Phase 10 — Reason Generation

Every output field must carry machine-readable reason codes and concise human-readable reasoning.

## Phase 11 — Backtest and Calibration

Test the complete production pipeline chronologically.

Calibrate thresholds per strategy, regime and symbol-behavior group.

## Phase 12 — Output Upgrade

Update text and JSON output while preserving deterministic serialization and CLI stability.

---

# 24. Non-Goals

This methodology upgrade must not:

* guarantee winning trades;
* force a minimum number of results;
* force every target to 10%;
* force every trade into a short holding window;
* use leverage return as expected market movement;
* combine indicators into an uncalibrated win probability;
* create candle-only strategies without context;
* add undocumented discretionary rules;
* redesign the entire Apex repository;
* create separate analysis logic for `scan` and `analyze`;
* fabricate unavailable order-flow or open-interest data.

---

# 25. Definition of Success

The upgrade succeeds when Apex can consistently explain:

```text
Why this coin?
Why this direction?
Why this strategy?
Why now?
Why this entry zone?
Why is another nearby entry better?
Why this invalidation?
Why this stop?
Why these targets?
Why could the move reach 3%, 5%, 10%, or more?
How long may the setup remain valid?
What evidence contradicts the trade?
Why was another candidate rejected?
```

The final product should not claim to predict the next trade with certainty.

It should identify objectively defined opportunities with:

* compatible market conditions;
* complete strategy rules;
* fresh entry geometry;
* controlled structural risk;
* realistic target room;
* explicit uncertainty;
* and evidence that can be tested over a meaningful sample.
