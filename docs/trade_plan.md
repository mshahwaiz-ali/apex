# Apex Trade Analysis Methodology Upgrade

## 1. Purpose

This document defines the methodology for improving Apex trade discovery and post-shortlist coin analysis.

Apex is already built. This work must not redesign the repository, replace the CLI, or create separate analysis engines.

The objective is to improve the quality, availability, ranking, and explanation of opportunities returned by:

```text
apex scan
apex analyze SYMBOL
```

Both commands must use the same shared trade-analysis core. The only difference is symbol selection:

- `apex scan` discovers and shortlists symbols first.
- `apex analyze SYMBOL` analyzes the requested symbol directly.

After symbol selection, both commands must apply identical market-state classification, strategy routing, setup detection, entry construction, stop placement, target projection, expiry, scoring, confidence, rejection, ranking, and output wording.

---

# 2. Product Objective

Apex should find the strongest currently available long and short opportunities without forcing trades and without hiding valid opportunities behind unnecessary universal rules.

The engine must answer, in order:

1. Is this market usable?
2. What is the current market state?
3. Which strategy families fit that state?
4. Is a measurable setup present?
5. Is the setup developing, confirmed, actionable, late, missed, or invalidated?
6. Is an entry valid near current market price?
7. Is a better nearby pullback, retest, reclaim, or rejection entry available?
8. Is a future trigger worth monitoring?
9. Where is the structural invalidation?
10. What stop follows from that invalidation?
11. What movement is realistically supported?
12. Which targets are reachable before major obstacles?
13. How long may the setup and trade remain valid?
14. What is the evidence-based confidence level?
15. Why was this candidate selected, downgraded, deferred, or rejected?

Apex must not start with:

> Which indicators are bullish?

It must start with:

> What is this market doing, where is price located, and which tested setup fits this condition?

---

# 3. Controlling Principles

## 3.1 Structure first

Market structure determines the setup. Indicators provide supporting, timing, or contradiction evidence.

Primary structural inputs include:

- swing highs and lows;
- trend sequences;
- support and resistance zones;
- range boundaries;
- breakouts and breakdowns;
- retests and polarity changes;
- trendlines and channels;
- liquidity sweeps and rejection;
- compression and expansion;
- failed patterns;
- location relative to higher-timeframe obstacles.

## 3.2 Context before candle shape

Candlestick evidence may strengthen, weaken, time, or warn about a setup. A candle pattern must not bypass regime compatibility, structural context, liquidity, stop validity, or target feasibility.

## 3.3 Pattern detection is not trade approval

A recognizable pattern may still be:

- incomplete;
- badly located;
- too late;
- blocked by nearby structure;
- incompatible with the market state;
- missing a valid stop;
- or unsupported by sufficient historical evidence.

## 3.4 Reject less, classify better

Apex must not manufacture trades. It must also not convert every imperfection into `NO_TRADE`.

Invalid conditions should block. Imperfect but usable conditions should normally:

- reduce component scores;
- lower confidence;
- change status;
- prefer another entry;
- shorten expiry;
- reduce target ambition;
- remove the runner;
- or produce explicit cautions.

## 3.5 No certainty wording

No single trade is guaranteed. Confidence describes evidence quality and historical calibration, not certainty about the next outcome.

## 3.6 No fixed universal target or holding period

Apex must not force every target toward 10% and must not force every setup into a quick execution window.

A structurally supported 3% move may be superior to an unsupported 10% target. A 10% or larger move is valid only when structure, volatility, pattern dimensions, and higher-timeframe room support it.

---

# 4. Shared Analysis Pipeline

```text
Market usability
→ Market-state classification
→ Multi-timeframe structural map
→ Strategy eligibility
→ Setup detection
→ Setup maturity
→ Entry opportunity search
→ Structural invalidation and stop
→ Target and movement projection
→ Duration and expiry estimation
→ Evidence and contradiction analysis
→ Confidence calibration
→ Hard blockers and soft penalties
→ Candidate ranking
→ Reasoned output
```

No later score may repair a logically invalid earlier stage.

Examples:

- strong volume cannot repair invalid structure;
- a distant target cannot repair a chased entry;
- multiple momentum indicators cannot repair a missing stop;
- a candle pattern cannot repair the wrong regime;
- a high discovery rank cannot guarantee a valid trade.

---

# 5. Market Usability

Before strategy analysis, Apex must assess whether execution-quality analysis is possible.

## 5.1 Inputs

- quote volume and trade participation;
- spread;
- candle continuity;
- sufficient history;
- data freshness;
- tick and quantity precision;
- usable volatility;
- noise and wick instability;
- order-book or ticker quality where available;
- abnormal data or exchange conditions.

## 5.2 States

```text
USABLE
USABLE_WITH_CAUTION
UNUSABLE
DATA_INCOMPLETE
```

`USABLE_WITH_CAUTION` is not automatically a rejection. It should carry measurable penalties and warnings.

---

# 6. Market-State Classification

Apex must classify the market before routing strategies.

## 6.1 Primary states

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
TRANSITIONAL
CHAOTIC
```

## 6.2 Secondary conditions

```text
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
MILD_HTF_CONFLICT
STRONG_HTF_CONFLICT
DIRECT_STRUCTURAL_OPPOSITION
```

## 6.3 Evidence families

Apex should use independent evidence families rather than indicator voting.

### Structure

- higher-high/higher-low or lower-high/lower-low sequences;
- swing quality and recency;
- structural breaks;
- range quality;
- channel position;
- support/resistance significance;
- level tests and reactions.

### Volatility

- ATR percentage;
- realized movement distribution;
- expansion and contraction;
- volatility percentile;
- impulse range versus normal range.

### Participation

- relative volume;
- impulse versus pullback volume;
- volume acceleration;
- breakout participation;
- retest contraction;
- open interest, taker flow, and liquidation data only when genuinely available.

### Location

- position inside the active range;
- distance from swing extremes;
- proximity to structural levels;
- distance from VWAP or trend mean;
- remaining room before major obstacles.

### Momentum

- return acceleration;
- persistence;
- momentum failure;
- divergence where objectively defined.

Correlated indicators must not be counted repeatedly. RSI and stochastic are not two independent momentum votes. Multiple EMAs are not several independent trend votes.

---

# 7. Strategy Routing

Apex must not evaluate every strategy equally on every symbol.

| Market state | Primary strategy families |
|---|---|
| Established uptrend | Trend pullback, first-pullback continuation, breakout continuation |
| Established downtrend | Short trend pullback, first-rally continuation, breakdown continuation |
| Clean range | Boundary reversal, failed boundary break |
| Compression | Expansion watch, confirmed breakout, confirmed breakdown |
| Confirmed breakout | Breakout continuation, breakout retest |
| Confirmed breakdown | Breakdown continuation, breakdown retest |
| Failed breakout | Failed-breakout reversal |
| Failed breakdown | Failed-breakdown reversal |
| Liquidity sweep at structure | Liquidity-rejection reversal |
| Exhaustion | Exit warning first; reversal only after strategy-specific confirmation |
| Chaotic structure | Normally no trade |

Each strategy must declare:

```text
strategy_id
strategy_version
compatible_states
prohibited_states
required_prior_structure
setup_timeframe
trigger_timeframe
risk_timeframe
target_timeframe
confirmation_policy
mandatory_evidence
optional_evidence
hard_blockers
soft_penalties
entry_models
invalidation_method
target_methods
expiry_policy
historical_segment_key
```

Strategy strictness must be strategy-specific. Momentum scalp, breakout retest, range reversal, and exhaustion reversal must not share one universal confirmation or R:R profile.

---

# 8. Setup Maturity and Confirmation

## 8.1 Setup states

```text
PATTERN_DEVELOPING
TRIGGER_PROVISIONAL
CONFIRMATION_PENDING_CLOSE
SETUP_CONFIRMED
RETEST_PENDING
RECLAIM_PENDING
ENTRY_AVAILABLE
ENTRY_LATE
ENTRY_MISSED
PATTERN_FAILED
INVALIDATED
```

## 8.2 Confirmation policies

Every strategy must use one explicit policy:

```text
close_required
intrabar_allowed
lower_timeframe_confirmation_allowed
retest_required
reclaim_required
mixed
```

Closed-candle confirmation must not be forced universally.

Examples:

- a major breakout may require a close beyond structure;
- a momentum scalp may permit intrabar execution with strict chase limits;
- a support rejection may use a completed lower-timeframe trigger;
- a retest strategy may require a held retest rather than another breakout close;
- a candle pattern whose geometry depends on the final close remains provisional until close.

`READY_NOW` means that the exact confirmation policy for that strategy is complete.

---

# 9. Entry Opportunity Search

For every valid setup, Apex must evaluate multiple entry possibilities independently.

## 9.1 Entry classes

```text
immediate_entry
aggressive_entry
preferred_nearby_entry
pullback_entry
retest_entry
reclaim_entry
rejection_entry
developing_future_entry
```

A preferred pullback must not hide a still-valid immediate entry.

Apex should be able to report:

```text
Immediate entry is valid but aggressive.
Preferred nearby entry offers better stop and reward geometry.
A retest entry remains valid if price returns to the structural zone.
```

## 9.2 Entry-zone fields

```text
zone_low
zone_high
ideal_entry
confirmation_level
maximum_chase
current_distance_percentage
current_distance_atr
entry_type
entry_quality
entry_reason
expiry_bars
```

Entry zones must be structural ranges, not arbitrary single prices.

## 9.3 Current-price handling

Apex should search near current market price first, but it must not force a current entry.

Possible outcomes:

- current price is inside a valid zone;
- current price permits an aggressive entry;
- current price is usable but a nearby entry is better;
- current price is too late, but a retest remains possible;
- current price has missed the setup;
- only a future trigger is identifiable.

---

# 10. Entry Status Model

```text
READY_NOW
AGGRESSIVE_NOW
VALID_WITH_CAUTION
PULLBACK_PREFERRED
RETEST_PREFERRED
RECLAIM_REQUIRED
APPROACHING_ENTRY
WAIT_FOR_CLOSE
DEVELOPING_SETUP
LATE_ENTRY
MISSED_ENTRY
INVALIDATED
NO_TRADE
```

## 10.1 `READY_NOW`

Requires:

- usable market;
- compatible strategy and regime;
- completed strategy-specific trigger;
- current price inside permitted geometry;
- valid structural invalidation and stop;
- sufficient realistic target room;
- no hard blocker.

It does not mean the trade is certain to win.

## 10.2 `VALID_WITH_CAUTION`

The trade remains executable but has meaningful soft penalties, such as mild higher-timeframe conflict, average participation, imperfect entry location, or reduced target room.

## 10.3 `NO_TRADE`

Use only when:

- no valid setup is identifiable;
- the strategy is logically incompatible with the market state;
- market execution is unusable;
- structural risk cannot be defined;
- or a hard blocker is active.

---

# 11. Structural Invalidation and Stop-Loss

Stops must come from the level that disproves the setup.

## 11.1 Hierarchy

1. Pattern invalidation
2. Swing invalidation
3. Structural-zone invalidation
4. Volatility buffer
5. Tick-size and round-number adjustment
6. Execution-cost allowance

## 11.2 Prohibited methods

- arbitrary fixed stop percentage;
- stop chosen only to manufacture desired R:R;
- stop inside the entry zone;
- stop on the wrong side of structure;
- stop based only on leverage or desired monetary loss;
- widening the stop after entry without new confirmed structure.

## 11.3 Required explanation

Every stop must explain:

- which structure invalidates the thesis;
- whether invalidation uses touch, wick, or close;
- why a volatility buffer is applied;
- what exact event proves the setup wrong.

---

# 12. Target and Movement Projection

Apex must derive targets from structure, not from a fixed percentage goal.

## 12.1 Target sources

1. Nearest structural obstacle
2. Prior swing high or low
3. Opposing range boundary
4. Breakout or breakdown measured move
5. Channel width
6. Pattern minimum objective
7. Higher-timeframe support or resistance
8. Volatility-supported extension
9. Conditional runner extension

## 12.2 Target roles

```text
TP1 = first realistic obstacle or risk-reduction level
TP2 = primary structural objective
TP3 = extended objective when continuation remains valid
RUNNER = conditional extension, never assumed
```

## 12.3 Movement envelope

```text
minimum_supported_move
primary_expected_move
extended_move
structural_max_before_major_obstacle
historical_volatility_range
```

Example:

```text
Minimum supported move: 2.6%
Primary structural objective: 5.1%
Extended objective: 8.4%
10%+ requires acceptance above the higher-timeframe resistance.
```

## 12.4 Reward evaluation

Do not impose one universal R:R threshold on every strategy.

Reward requirements should depend on:

- strategy family;
- expected hit rate;
- historical expectancy;
- partial exits;
- fees and slippage;
- holding duration;
- market state;
- target structure;
- entry quality.

A scalp may accept lower R:R when historically supported. A reversal may require higher potential reward. A range trade may use the opposing boundary. A multi-target plan may use blended expectancy.

No threshold should be presented as validated unless it was tested on relevant out-of-sample data.

---

# 13. Duration and Expiry

Expected holding time must be derived from:

- setup and trigger timeframes;
- pattern width and age;
- volatility;
- distance to target;
- trend state;
- expected retest behavior;
- historical time-to-target for comparable setups.

## 13.1 Output fields

```text
hold_category
expected_hold_min
expected_hold_max
expected_bars
setup_expiry_bars
expiry_reason
```

Possible categories:

```text
MICRO_SCALP
SCALP
INTRADAY
MULTI_SESSION
SWING
```

The category follows the setup. It does not determine it.

---

# 14. Hard Blockers and Soft Penalties

## 14.1 Hard blockers

Hard blockers should be minimal and explicit:

```text
UNUSABLE_MARKET
STALE_OR_INCOMPLETE_DATA
STRUCTURALLY_INVALIDATED
WRONG_STRATEGY_FOR_STATE
NO_DEFINABLE_INVALIDATION
CORRUPT_STOP_GEOMETRY
CLEARLY_MISSED_ENTRY
NO_REALISTIC_TARGET_ROOM
PATTERN_FAILED
DIRECT_STRUCTURAL_OPPOSITION
```

## 14.2 Soft penalties

These normally reduce quality rather than block:

- mild higher-timeframe conflict;
- average volume;
- incomplete optional confluence;
- slightly extended but usable entry;
- uncertain duration;
- weaker candle evidence;
- reduced but acceptable target room;
- absence of a conservative retest;
- higher volatility;
- one contradictory optional signal.

Several soft penalties may cross a configured quality floor, but the engine must show exactly how and why. There must be no hidden rejection inside an opaque overall score.

---

# 15. Higher-Timeframe Conflict

Classify conflict as:

```text
ALIGNED
MILD_CONFLICT
STRONG_CONFLICT
DIRECT_STRUCTURAL_OPPOSITION
```

Behavior:

- `ALIGNED`: normal eligibility;
- `MILD_CONFLICT`: soft penalty;
- `STRONG_CONFLICT`: permit only an explicitly supported countertrend, reversal, range, or scalp strategy;
- `DIRECT_STRUCTURAL_OPPOSITION`: hard blocker when no strategy-specific justification exists.

Valid countertrend trades should normally have:

- shorter target expectations;
- shorter expiry;
- lower confidence;
- stronger confirmation requirements;
- explicit countertrend warnings.

---

# 16. Scoring Framework

A single blended confidence score is insufficient.

## 16.1 Component scores

```text
market_quality_score
regime_fit_score
structure_quality_score
setup_completeness_score
confirmation_quality_score
entry_quality_score
risk_geometry_score
target_quality_score
timeframe_alignment_score
participation_score
data_quality_score
historical_edge_score
contradiction_penalty
overall_trade_quality_score
```

## 16.2 Rules

- Scores describe analytical quality, not certainty.
- Hard blockers are explicit gates, not low scores.
- Missing mandatory evidence cannot be repaired by optional evidence.
- Optional evidence adjusts quality.
- Correlated indicators cannot be counted repeatedly.
- Ranking eligibility and execution eligibility remain separate.
- A lower-ranked valid trade may still be displayed.

---

# 17. Confidence Model

Apex may display a confidence level, but it must be reasoned and calibrated.

## 17.1 Confidence dimensions

```text
setup_confidence
execution_confidence
target_confidence
data_confidence
historical_confidence
overall_confidence
```

## 17.2 Confidence labels

```text
VERY_LOW
LOW
MODERATE
HIGH
VERY_HIGH
```

Numeric percentages must not be shown as win probability unless calibrated from relevant untouched historical data.

When calibrated, output should separate:

```text
model_estimated_success_rate
sample_size
confidence_interval
segment_definition
out_of_sample_period
calibration_version
```

## 17.3 Evidence hierarchy

Confidence should be based mainly on:

1. Regime and strategy fit
2. Structural completeness
3. Entry location and freshness
4. Stop and invalidation quality
5. Realistic room to targets
6. Multi-timeframe relationship
7. Participation confirmation
8. Historical performance in the same strategy/regime/symbol-behavior segment
9. Data quality
10. Contradictions and uncertainty

## 17.4 Confidence reasoning

Every result must state:

- top supporting reasons;
- strongest contradiction;
- missing evidence;
- whether confidence is rule-based or historically calibrated;
- what would raise confidence;
- what would invalidate or lower confidence.

Example:

```text
Overall confidence: HIGH, rule-based
Primary reasons:
- 1h trend and 15m setup are aligned.
- Breakout closed beyond a repeatedly tested zone.
- Retest held with contracting volume.
- Entry remains near structural support.
- TP1 offers acceptable reward before the next obstacle.

Main contradiction:
- 4h resistance limits the extended target.

Historical calibration:
- Not yet available for this exact strategy/regime segment.
```

A high rule-based confidence label must never be described as a verified win probability.

---

# 18. Candidate Ranking

Apex requires two distinct ranks.

## 18.1 Discovery rank

Used to choose which symbols receive expensive analysis.

Inputs may include:

- liquidity;
- spread;
- movement;
- acceleration;
- relative volume;
- usable volatility;
- structure proximity;
- directional clarity;
- freshness.

## 18.2 Trade rank

Used after complete analysis.

Inputs should include:

- strategy and regime fit;
- setup maturity;
- entry quality;
- structural risk;
- target feasibility;
- expected value after costs;
- timeframe relationship;
- participation;
- historical calibration;
- data quality;
- contradiction penalties.

A high discovery rank can result in no valid trade. A quieter coin can produce superior trade geometry.

## 18.3 Candidate comparison

Top candidates should be compared on the same dimensions rather than only by total score.

Example comparison fields:

```text
best_current_entry
best_reward_geometry
strongest_structure
highest_historical_edge
lowest_execution_risk
largest_supported_move
fastest_expected_resolution
```

---

# 19. Coin-Specific Adaptation

Do not create manually customized strategies for every coin.

Create versioned historical behavior profiles:

```text
normal_atr_by_timeframe
normal_spread
normal_volume
impulse_distribution
pullback_depth_distribution
breakout_follow_through_rate
retest_frequency
failed_breakout_rate
average_favorable_excursion
average_adverse_excursion
median_time_to_target
median_time_to_invalidation
trend_persistence
range_frequency
wick_behavior
```

Profiles may adapt thresholds while preserving strategy definitions.

Examples:

- volatile altcoins may need wider ATR-normalized zones;
- liquid majors may support tighter triggers;
- frequent false-breakout coins may require retests;
- strong continuation coins may permit earlier entries;
- mean-reverting coins may route more often to range strategies.

All adaptations must be reproducible, time-safe, versioned, and validated on unseen data.

---

# 20. Historical Edge and Success Probability

The goal is not merely to create more signals. The goal is to find segments with repeatable positive expectancy.

Historical evaluation must be segmented by:

```text
strategy
market_state
direction
symbol_behavior_group
volatility_bucket
entry_type
confirmation_policy
timeframe_combination
session_or_time_bucket_if_relevant
```

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
entry_fill_rate
missed_entry_rate
expiry_rate
time_to_entry
time_to_target
time_to_stop
TP1_rate
TP2_rate
TP3_rate
stop_rate
```

Success probability must never be inferred from the current indicator count. It may only come from the historical distribution of genuinely comparable, out-of-sample setups.

Minimum requirements before displaying a calibrated probability:

- sufficient sample size;
- stable results across time splits;
- acceptable confidence interval;
- no single-symbol or single-period dependence;
- no look-ahead leakage;
- matching production rules;
- versioned calibration data.

When evidence is insufficient, output:

```text
Historical probability unavailable or insufficiently calibrated.
```

---

# 21. Output Reasoning

Every selected setup must explain:

## Why this coin

- discovery reason;
- liquidity and spread;
- movement and volatility;
- market-state opportunity.

## Why this direction

- higher-timeframe structure;
- setup-timeframe structure;
- local trigger;
- opposing evidence.

## Why this strategy

- compatible state;
- exact setup conditions;
- confirmation policy;
- why alternatives ranked lower.

## Why this entry

- zone construction;
- current-price relationship;
- preferred alternative;
- maximum chase;
- entry expiry.

## Why this stop

- invalidating structure;
- buffer;
- exact failure event.

## Why these targets

- source of each target;
- expected move percentage;
- R multiple;
- obstacles;
- conditions for extended targets.

## Why this duration

- setup timeframe;
- target distance;
- volatility;
- comparable historical behavior.

## Why this confidence

- component scores;
- historical segment if available;
- supporting evidence;
- contradictions;
- uncertainty;
- missing data.

---

# 22. Example Result

```text
Symbol: XYZUSDT
Direction: LONG
Strategy: Breakout Retest
Status: VALID_WITH_CAUTION

Market state:
Confirmed 15m range breakout inside a 1h uptrend.

Current price:
1.245

Immediate entry:
1.238–1.247
Valid but aggressive near the upper edge of permitted geometry.

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
6–24 hours based on setup width, ATR, and target distance.

Overall confidence:
HIGH, rule-based; not a calibrated win probability.

Primary reasons:
- 1h and 15m structures are aligned.
- Breakout closed above a repeatedly tested zone.
- Retest remains structurally valid.
- Pullback volume is contracting.
- TP1 provides acceptable reward before resistance.

Main contradiction:
- Current price is above ideal entry.
- TP3 requires acceptance above TP2 resistance.

Historical calibration:
Insufficient sample for this exact strategy/regime segment.
```

---

# 23. Validation and Trade-Suppression Testing

No methodology change is complete without chronological testing.

Required tests:

- closed-candle replay without leakage;
- intrabar policies using only data available at that moment;
- realistic entry-touch behavior;
- conservative same-candle stop/target ambiguity;
- fees and slippage;
- missed entries and expiry;
- partial targets;
- strategy and regime segmentation;
- long and short separation;
- symbol-profile validation;
- train, validation, and untouched test splits.

Measure whether strict rules suppress valid opportunities:

```text
eligible_setup_count
approved_trade_count
hard_rejection_rate
soft_penalty_rate
no_trade_rate
aggressive_entry_rate
preferred_entry_rate
entry_fill_rate
missed_entry_rate
provisional_to_confirmed_rate
provisional_to_failed_rate
valid_trade_suppression_rate
opportunity_cost_of_waiting
```

Compare controlled variants:

- universal close requirement versus strategy-specific confirmation;
- immediate entry versus preferred pullback;
- universal R:R versus strategy-calibrated expectancy;
- hard HTF rejection versus graded conflict;
- generic thresholds versus symbol-behavior adaptation.

Do not optimize only for more trades or higher win rate. Optimize for stable positive expectancy, realistic execution, controlled drawdown, sufficient sample size, and robustness across periods and symbols.

---

# 24. Codex Implementation Sequence

## Phase 1 — Current Pipeline Audit

Map exact code paths for scan, analyze, screening, shortlisting, feature calculation, environment classification, strategy routing, candidate generation, entry geometry, stop calculation, target calculation, scoring, ranking, presentation, and backtesting.

No behavior change in this phase.

## Phase 2 — Shared Contracts

Create or refine normalized contracts for market state, strategy candidate, entry opportunity, invalidation, target candidate, evidence, contradiction, confidence, rejection, and duration.

## Phase 3 — Market-State Classifier

Implement deterministic primary and secondary state classification with synthetic and historical tests.

## Phase 4 — Strategy Eligibility Matrix

Make every strategy declare compatible states, mandatory conditions, optional evidence, confirmation policy, hard blockers, and soft penalties.

## Phase 5 — Multi-Entry Search

Support immediate, aggressive, preferred pullback, retest, reclaim, rejection, and developing future entries.

## Phase 6 — Stop and Invalidation Engine

Separate thesis invalidation, stop price, buffer, and execution warning.

## Phase 7 — Structural Target Engine

Generate target candidates, movement envelopes, and conditional extensions without fixed percentage forcing.

## Phase 8 — Duration and Expiry

Derive expected holding time and setup expiry from timeframe, structure, volatility, target distance, and historical behavior.

## Phase 9 — Scoring and Confidence

Implement component scores, explicit gates, evidence-based confidence labels, contradiction handling, and optional historical calibration.

## Phase 10 — Candidate Comparison and Reasons

Provide comparable ranking dimensions, machine-readable reason codes, and concise human-readable explanations.

## Phase 11 — Backtest and Calibration

Run production-equivalent chronological testing, calibrate by strategy/regime/behavior segment, and measure trade suppression.

## Phase 12 — Output Upgrade

Update text and JSON output while preserving deterministic serialization and CLI stability.

---

# 25. Non-Goals

This upgrade must not:

- guarantee winning trades;
- force a minimum number of results;
- force every target to 10%;
- force every trade into a short holding window;
- use leverage return as expected market movement;
- display uncalibrated percentages as win probability;
- create candle-only strategies without context;
- add undocumented discretionary rules;
- redesign the repository;
- create separate analysis logic for scan and analyze;
- fabricate unavailable order-flow, open-interest, or liquidation data;
- optimize only for win rate or trade count.

---

# 26. Definition of Success

The upgrade succeeds when Apex can consistently explain:

```text
Why this coin?
Why this direction?
Why this strategy?
Why now?
Why this entry zone?
Is the current entry valid, aggressive, late, or missed?
Is there a better nearby entry?
Why this invalidation and stop?
Why these targets?
Why could movement reach 3%, 5%, 10%, or more?
How long may the setup remain valid?
What is the confidence level?
Is confidence rule-based or historically calibrated?
Which evidence matters most?
What contradicts the trade?
Why was another candidate ranked lower or rejected?
```

The final product should identify objectively defined opportunities with compatible market conditions, strategy-specific rules, fresh entry geometry, controlled structural risk, realistic target room, explicit uncertainty, transparent confidence, and evidence that can be validated over meaningful samples.
