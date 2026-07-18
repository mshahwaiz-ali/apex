# Apex Trade Analysis Methodology

## 1. Purpose and authority

This document is the implementation authority for improving Apex trade discovery, analysis, ranking, and output.

Apex is already built. The methodology must be integrated into the existing architecture rather than replacing the repository, CLI, providers, contracts, or working execution modules.

The two user-facing analysis paths must share one trade-analysis core:

```text
apex scan
apex analyze SYMBOL
```

The only difference is symbol selection:

- `apex scan` discovers and shortlists symbols before full analysis.
- `apex analyze SYMBOL` sends the requested symbol directly into the same full analysis pipeline.

After symbol selection, both commands must use identical market-state classification, feature calculation, strategy routing, setup detection, entry construction, invalidation, stop placement, target projection, duration, scoring, rejection, ranking, and wording.

---

# 2. Product objective

Apex should identify the strongest currently available long and short opportunities without forcing trades, chasing price, or hiding usable setups behind universal rules.

The objective is not to predict the next candle with certainty. It is to find objectively defined situations where:

- the market is executable;
- the current state matches a tested strategy;
- price is at a meaningful location;
- entry risk can be structurally defined;
- realistic target room exists after costs;
- evidence is stronger than contradiction;
- and the setup belongs to a historically positive or still-testable segment.

A high-profit opportunity means **high supported movement relative to controlled risk**, not merely a coin with a large recent percentage move.

The engine must answer:

1. Is the symbol liquid and usable?
2. What is the higher-timeframe and local market state?
3. Where is price relative to structure, value, and major obstacles?
4. Which strategies are compatible with that state?
5. Is a measurable setup developing or complete?
6. Is current price executable, aggressive, late, missed, or invalidated?
7. Is a better nearby pullback, retest, reclaim, or rejection entry available?
8. What exact event disproves the trade thesis?
9. What stop follows from that invalidation?
10. What movement is structurally and statistically supportable?
11. Which targets are reachable before opposing structure?
12. How long may the setup and position reasonably remain valid?
13. Which independent evidence families support or contradict the trade?
14. Is confidence rule-based or historically calibrated?
15. Why was this candidate selected, downgraded, deferred, or rejected?

---

# 3. Research-derived controlling principles

The methodology combines three source roles:

- **John J. Murphy:** trend, support and resistance, price patterns, volume/open interest, confirmation, multi-timeframe context, and measured objectives.
- **Steve Nison:** candlestick context, completion, reversal warnings, continuation signals, and confluence with Western technical tools.
- **Mark Douglas:** probability, predefined risk, repeatable execution, sample-based edge evaluation, and non-certain wording.

## 3.1 Structure first

Market structure defines the opportunity. Indicators support classification, timing, participation, volatility, or contradiction.

Primary structural inputs:

- swing highs and lows;
- higher-high/higher-low and lower-high/lower-low sequences;
- support and resistance zones;
- range boundaries and midpoint/value areas;
- breakouts, breakdowns, acceptance, and rejection;
- retests and change of polarity;
- trendlines and channels;
- compression and expansion;
- liquidity sweeps;
- failed breakouts and failed breakdowns;
- pattern dimensions;
- proximity to higher-timeframe obstacles.

Apex must not begin with “which indicators are bullish?” It must begin with:

> What is the market doing, where is price located, and which strategy fits this condition?

## 3.2 Indicators are evidence, not votes

Indicators must be grouped by the market property they measure. Correlated indicators cannot be counted as independent confirmations.

Examples:

- RSI and stochastic are both momentum oscillators.
- EMA 9, EMA 20, and EMA 50 are not three independent trend votes.
- MACD direction and two-EMA crossover overlap materially.
- Bollinger width and ATR both measure volatility, though differently.

Apex should select a small representative set per evidence family and record redundancy explicitly.

## 3.3 Context before candle name

Candlestick patterns are a timing and confirmation layer. They must not create a trade by themselves.

A candle signal is meaningful only after checking:

- prior trend or range context;
- structural location;
- completion state;
- confirmation policy;
- participation;
- stop validity;
- target room;
- and higher-timeframe compatibility.

A reversal candle means the prior move may weaken, pause, range, or reverse. It does not automatically authorize an opposite-direction position.

## 3.4 Pattern detection is not trade approval

A recognizable pattern may still be:

- incomplete;
- badly located;
- against the dominant structure;
- too late;
- blocked by nearby resistance or support;
- caused by thin liquidity;
- missing a valid stop;
- or unsupported by historical performance.

## 3.5 Probability, not certainty

Every trade outcome is uncertain. An edge means that a defined setup has produced a favorable distribution over a meaningful sample, not that the next trade will win.

Apex must never use wording such as:

- guaranteed;
- safe trade;
- certain breakout;
- will reverse;
- cannot fail.

## 3.6 Risk must exist before approval

No trade can be executable until Apex can state:

- the thesis;
- structural invalidation;
- stop price;
- expected slippage and fees;
- quantity and maximum loss;
- and the conditions under which the setup expires.

## 3.7 No universal target, R:R, or holding period

Apex must not force every setup toward 10%, one universal reward-to-risk ratio, or a short execution window.

A supported 3% movement can be superior to an unsupported 10% target. A 10% or larger projection is valid only when structure, volatility, pattern dimensions, participation, and higher-timeframe room support it.

## 3.8 Reject less, classify better

Hard blockers should be minimal and logical. Imperfect but usable conditions should usually:

- reduce a component score;
- lower confidence;
- change the entry status;
- prefer a better entry;
- shorten expiry;
- reduce target ambition;
- remove the runner;
- or add a warning.

---

# 4. Shared analysis pipeline

```text
Symbol selection
→ Market usability
→ Broad-market context
→ Multi-timeframe structural map
→ Market-state classification
→ Indicator/evidence calculation
→ Strategy eligibility
→ Setup detection
→ Setup maturity and confirmation
→ Multi-entry opportunity search
→ Structural invalidation and stop
→ Target and movement projection
→ Duration and expiry
→ Risk and execution geometry
→ Evidence and contradiction analysis
→ Hard blockers and soft penalties
→ Historical calibration
→ Trade ranking
→ Reasoned output
```

No later score may repair a logically invalid earlier stage.

Examples:

- strong volume cannot repair invalid structure;
- an oscillator extreme cannot create a reversal without price confirmation;
- a distant target cannot repair a chased entry;
- multiple momentum indicators cannot repair a missing stop;
- a candle pattern cannot repair the wrong regime;
- a high discovery rank cannot guarantee a valid trade.

---

# 5. Coin discovery

Discovery and trade approval are separate.

## 5.1 Discovery universe

Start from exchange-supported perpetual futures symbols, then remove symbols that fail basic execution requirements:

- inactive or newly listed without sufficient history;
- inadequate quote volume or trade count;
- unacceptable spread;
- abnormal candle gaps or stale data;
- unusable tick/quantity precision;
- excessive wick noise relative to body/range;
- clearly manipulated or discontinuous behavior;
- unavailable risk or market metadata required by the current mode.

Do not use survivorship-biased static historical universes in backtests. The historical universe must contain symbols that were actually available at each time.

## 5.2 Discovery lanes

Apex should run separate discovery lanes so that quiet high-quality setups are not buried by raw gainers.

### Lane A — Trend continuation

Search for:

- persistent directional structure;
- healthy pullback or first pullback;
- trend-aligned momentum;
- pullback volume contraction;
- room to the next major obstacle.

### Lane B — Compression and expansion

Search for:

- volatility contraction;
- range or band compression;
- repeated level pressure;
- participation beginning to expand;
- breakout or breakdown proximity.

### Lane C — Fresh breakout or breakdown

Search for:

- decisive structural breach;
- close/acceptance beyond the level when required;
- volume or trade participation expansion;
- limited extension from the breakout zone;
- retest availability.

### Lane D — Fast mover or top gainer/loser

Search for:

- abnormal return acceleration;
- relative volume expansion;
- volatility expansion;
- open-interest participation when available;
- remaining room versus already-consumed movement;
- continuation, first-pullback, exhaustion, or failed-break classification.

A large move alone is not a long or short signal.

### Lane E — Range boundary and liquidity rejection

Search for:

- clean repeated boundaries;
- sweep beyond support or resistance;
- reclaim/rejection;
- acceptable distance to the opposite range objective;
- evidence that the market is still ranging rather than transitioning.

### Lane F — Relative strength and weakness

Compare symbols against a broad crypto benchmark and their own recent history:

- relative return persistence;
- performance during benchmark pullbacks/rallies;
- participation-adjusted strength;
- structure quality;
- and whether dispersion is becoming extreme.

Relative strength is a shortlist feature, not automatic trade approval.

## 5.3 Discovery rank

Discovery rank chooses which symbols receive expensive analysis. It may use:

```text
liquidity_quality
spread_quality
movement_percentile
return_acceleration
relative_volume
volatility_state
compression_or_expansion
structure_proximity
directional_clarity
freshness
relative_strength_or_weakness
open_interest_change_if_available
```

Raw percentage gain must not dominate the score. Caps or nonlinear transforms should prevent one extreme feature from overwhelming execution quality and structure.

---

# 6. Market usability and broad-market context

## 6.1 Usability states

```text
USABLE
USABLE_WITH_CAUTION
UNUSABLE
DATA_INCOMPLETE
```

Inputs:

- quote volume;
- trade participation;
- spread and estimated slippage;
- candle continuity;
- sufficient lookback;
- data freshness;
- tick and quantity precision;
- ATR and realized volatility;
- wick instability;
- order-book quality when available;
- abnormal exchange conditions.

`USABLE_WITH_CAUTION` applies measurable penalties and warnings. It is not automatically `NO_TRADE`.

## 6.2 Broad-market context

Before analyzing an altcoin, Apex should classify:

- BTC and, where useful, ETH direction and volatility;
- broad risk-on/risk-off behavior;
- market breadth;
- cross-symbol correlation;
- cross-sectional dispersion;
- and whether market leadership is concentrated or broad.

Broad context may alter ranking, confidence, and target ambition. It should not automatically block a symbol-specific setup unless direct structural opposition exists.

---

# 7. Multi-timeframe framework

Timeframes have roles rather than equal votes.

```text
context_timeframe  → dominant structure and major obstacles
setup_timeframe    → pattern and trade thesis
trigger_timeframe  → entry timing and confirmation
risk_timeframe     → structural invalidation
management_timeframe → lifecycle decisions
```

Example mappings may be configured by strategy:

- micro scalp: 15m context, 3m setup, 1m trigger;
- intraday: 4h/1h context, 15m setup, 3m/5m trigger;
- multi-session: daily/4h context, 1h setup, 15m trigger.

A lower timeframe may refine entry but must not erase a direct higher-timeframe obstacle. Higher-timeframe conflict must be graded, not treated as a universal rejection.

---

# 8. Market-state classification

## 8.1 Primary states

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

## 8.2 Secondary conditions

```text
VOLATILITY_EXPANSION
VOLATILITY_CONTRACTION
VOLUME_EXPANSION
VOLUME_DIVERGENCE
OPEN_INTEREST_EXPANSION
OPEN_INTEREST_CONTRACTION
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

State classification must use deterministic rules and expose the evidence that produced the state.

---

# 9. Indicator and evidence policy

Apex should use indicators, but each indicator must have an explicit role.

## 9.1 Trend and mean

Preferred tools:

- market-structure sequence;
- EMA slope and ordered stack;
- distance from EMA or anchored/session VWAP where available;
- optional ADX or trend-efficiency measure.

Use cases:

- identify trend direction and persistence;
- detect pullback toward a dynamic mean;
- measure extension;
- detect trend deterioration.

Do not enter solely because of an EMA crossover. Crossovers are lagging confirmation and must be interpreted with structure and location.

## 9.2 Momentum

Preferred tools:

- RSI level, range behavior, slope, failure swing, and divergence;
- MACD line/signal state and histogram acceleration/deceleration;
- rate of change or normalized return persistence.

Rules:

- RSI overbought is not an automatic short.
- RSI oversold is not an automatic long.
- strong trends may remain extreme.
- divergence is supporting evidence, not a standalone trigger.
- MACD should help classify momentum continuation or deterioration, not duplicate EMA votes.

## 9.3 Volume and participation

Preferred tools:

- relative volume versus the same timeframe and time-of-week distribution;
- volume acceleration;
- impulse volume versus pullback volume;
- breakout volume;
- retest contraction;
- OBV or cumulative-volume trend only as secondary confirmation;
- trade-count or taker-volume measures when reliable.

Volume should answer whether participation supports the move. High volume after extreme extension may represent climax rather than continuation.

## 9.4 Volatility

Preferred tools:

- ATR and ATR percentage;
- realized-volatility percentile;
- Bollinger Band width or equivalent compression measure;
- candle-range expansion relative to recent distribution;
- volatility-of-volatility where useful.

Bollinger Bands are not automatic reversal boundaries. In trends, price can walk the band. Their strongest role is volatility state, compression, expansion, mean distance, and conditional target context.

## 9.5 Candlestick and price-action evidence

Candidate patterns may include:

- hammer / hanging man;
- shooting star / inverted hammer;
- bullish or bearish engulfing;
- piercing / dark-cloud style rejection;
- morning/evening star;
- doji and long-legged indecision;
- three-method continuation;
- strong expansion candle;
- inside-bar compression;
- rejection wick;
- reclaim close;
- failed breakout candle.

Pattern fields:

```text
pattern_id
pattern_direction
completion_state
prior_move_requirement
location_quality
body_ratio
wick_ratios
relative_range
close_location
volume_context
confirmation_level
invalidation_level
```

A pattern depending on the final close remains provisional until close. Strategy-specific lower-timeframe confirmation may permit earlier execution only when explicitly configured.

## 9.6 Futures-specific evidence

Use only when genuinely available and reliable:

- open interest and its change;
- funding rate and funding percentile;
- basis;
- taker buy/sell imbalance;
- liquidation intensity;
- mark/index divergence.

Interpretation must be conditional:

- price up + OI up can indicate new participation;
- price up + OI down may indicate short covering;
- price down + OI up can indicate new shorts;
- price down + OI down may indicate long liquidation.

These are hypotheses requiring context, not deterministic direction signals.

## 9.7 Indicator redundancy control

Each evidence observation must declare:

```text
evidence_family
source_indicator
normalized_strength
freshness
independence_group
supports
contradicts
```

Only one capped contribution per highly correlated independence group should affect the aggregate score.

---

# 10. Strategy routing

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
| Fast mover | Momentum continuation, first pullback, exhaustion watch, failed-break reversal |
| Exhaustion | Exit warning first; reversal only after confirmation |
| Chaotic | Normally no trade |

Every strategy must declare:

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

Strategy strictness must be strategy-specific. A momentum scalp, breakout retest, range reversal, and exhaustion reversal cannot share one universal confirmation or reward requirement.

---

# 11. Setup maturity and confirmation

## 11.1 Internal maturity states

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

## 11.2 Confirmation policies

```text
close_required
intrabar_allowed
lower_timeframe_confirmation_allowed
retest_required
reclaim_required
mixed
```

Examples:

- a major breakout may require a close or acceptance beyond structure;
- a momentum scalp may permit intrabar execution with strict chase limits;
- a rejection may use a completed lower-timeframe trigger;
- a retest strategy requires a held retest rather than another breakout close;
- a candle whose definition depends on close remains provisional.

---

# 12. Entry opportunity search

Apex must evaluate multiple entry possibilities independently.

## 12.1 Entry classes

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

## 12.2 Entry-zone construction

Entry zones must come from one or more of:

- structural support/resistance band;
- breakout/retest band;
- candle body/wick rejection area;
- prior swing cluster;
- polarity zone;
- VWAP/EMA confluence area;
- volatility-normalized trigger band;
- retracement band of a valid impulse.

Required fields:

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

## 12.3 Current-price handling

Possible outcomes:

- current price is inside a valid entry zone;
- current price permits an aggressive entry;
- current price is usable but a nearby entry is better;
- current price is late but a retest remains possible;
- current price has missed the setup;
- only a future trigger is identifiable.

## 12.4 Chase control

Maximum chase must be derived from:

- distance from structural entry;
- ATR-normalized extension;
- consumed target room;
- stop expansion;
- historical adverse selection after similar extensions;
- and strategy-specific tolerance.

A trade becomes late when improved momentum is outweighed by degraded entry and target geometry.

---

# 13. User-facing entry status

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

`READY_NOW` means the strategy-specific execution conditions are complete. It does not mean the trade is certain to win.

`NO_TRADE` is used only when no valid setup exists, the market is unusable, the strategy is incompatible, structural risk cannot be defined, or a hard blocker is active.

---

# 14. Structural invalidation and stop-loss

Stops must follow the level or event that disproves the setup.

Hierarchy:

1. pattern invalidation;
2. swing invalidation;
3. structural-zone invalidation;
4. volatility buffer;
5. tick-size and round-number adjustment;
6. execution-cost allowance.

Every stop must state:

- invalidating structure;
- touch, wick, or close rule;
- volatility buffer;
- exact failure event;
- estimated slippage;
- and why the stop is not inside normal noise.

Prohibited:

- arbitrary fixed stop percentage;
- stop selected only to manufacture R:R;
- stop inside the entry zone;
- stop on the wrong side of structure;
- stop based only on leverage or desired monetary loss;
- widening after entry without newly confirmed structure.

Leverage changes required margin and liquidation distance. It must never change the structural stop or make an invalid trade valid.

---

# 15. Target and movement projection

## 15.1 Target sources

1. nearest structural obstacle;
2. prior swing high/low;
3. opposing range boundary;
4. breakout/breakdown measured move;
5. channel width;
6. validated pattern objective;
7. higher-timeframe support/resistance;
8. volatility-supported extension;
9. conditional runner extension.

Candlestick patterns alone do not provide reliable price targets.

## 15.2 Target roles

```text
TP1 = first realistic obstacle or risk-reduction level
TP2 = primary structural objective
TP3 = extended objective when continuation remains valid
RUNNER = conditional extension, never assumed
```

## 15.3 Movement envelope

```text
minimum_supported_move
primary_expected_move
extended_move
structural_max_before_major_obstacle
historical_volatility_range
```

## 15.4 Reward evaluation

Do not impose one universal R:R threshold. Requirements depend on:

- strategy family;
- historical hit rate and expectancy;
- target fill distribution;
- partial exits;
- fees and slippage;
- market state;
- holding duration;
- entry quality;
- tail and liquidation risk.

A scalp may accept lower initial R:R only when historical expectancy after costs supports it. A countertrend reversal should generally require stronger geometry.

---

# 16. Duration and expiry

Expected holding time and setup expiry derive from:

- context/setup/trigger timeframes;
- pattern width and age;
- volatility;
- distance to target;
- trend persistence;
- expected retest behavior;
- median time-to-target and time-to-invalidation for comparable setups.

Fields:

```text
hold_category
expected_hold_min
expected_hold_max
expected_bars
setup_expiry_bars
expiry_reason
```

Categories:

```text
MICRO_SCALP
SCALP
INTRADAY
MULTI_SESSION
SWING
```

The setup determines the category. The category must not force the setup into an arbitrary duration.

---

# 17. Hard blockers and soft penalties

## 17.1 Hard blockers

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
LIQUIDATION_BUFFER_UNSAFE
```

## 17.2 Soft penalties

- mild higher-timeframe conflict;
- average participation;
- incomplete optional confluence;
- slightly extended but usable entry;
- uncertain duration;
- weaker candle evidence;
- reduced but acceptable target room;
- absence of a conservative retest;
- elevated volatility;
- one contradictory optional signal;
- unusually positive/negative funding;
- low-confidence derivatives data.

Several soft penalties may push a candidate below a configured quality floor, but the output must show how. No hidden rejection may occur inside an opaque total score.

---

# 18. Scoring and confidence

## 18.1 Component scores

```text
market_quality_score
broad_context_score
regime_fit_score
structure_quality_score
setup_completeness_score
confirmation_quality_score
entry_quality_score
risk_geometry_score
target_quality_score
timeframe_alignment_score
participation_score
volatility_opportunity_score
derivatives_context_score
data_quality_score
historical_edge_score
contradiction_penalty
overall_trade_quality_score
```

Rules:

- scores describe analytical quality, not certainty;
- hard blockers are gates, not low scores;
- missing mandatory evidence cannot be repaired by optional evidence;
- optional evidence adjusts quality;
- correlated indicators are capped by independence group;
- discovery rank and execution eligibility remain separate;
- a lower-ranked valid trade may still be displayed.

## 18.2 Confidence dimensions

```text
setup_confidence
execution_confidence
target_confidence
data_confidence
historical_confidence
overall_confidence
```

Labels:

```text
VERY_LOW
LOW
MODERATE
HIGH
VERY_HIGH
```

Numeric percentages must not be shown as win probability unless calibrated from untouched out-of-sample data.

Calibrated output must include:

```text
model_estimated_success_rate
sample_size
confidence_interval
segment_definition
out_of_sample_period
calibration_version
```

Every result must show the strongest support, strongest contradiction, missing evidence, calibration state, and what would invalidate the setup.

---

# 19. Trade ranking

Trade rank is calculated only after full analysis.

Inputs:

- strategy/regime fit;
- setup maturity;
- entry freshness;
- structural risk;
- target feasibility;
- expected value after costs;
- timeframe relationship;
- participation;
- volatility opportunity;
- derivatives context when available;
- historical calibration;
- data quality;
- contradiction penalties.

Top candidates should be compared using dimensions, not only a total number:

```text
best_current_entry
best_reward_geometry
strongest_structure
highest_historical_edge
lowest_execution_risk
largest_supported_move
fastest_expected_resolution
```

A high discovery rank may still result in no trade. A quieter symbol may produce superior trade geometry.

---

# 20. Historical edge and research standard

## 20.1 Why indicator claims require testing

The books define analytical tools and disciplined usage; they do not prove that every named pattern or default indicator period is profitable in modern crypto.

External empirical research is mixed:

- several studies report time-series or short-horizon momentum;
- other studies find weak or absent cross-sectional momentum;
- recent work shows results can disappear after realistic liquidation, liquidity, survivorship, and tail-risk assumptions;
- state transitions materially affect momentum performance;
- liquid major coins may behave differently from thin altcoins.

Therefore Apex must not label RSI, MACD, EMA, Bollinger Bands, candlesticks, volume, or momentum as “proven profitable” in isolation. Their contribution must be validated as part of a complete strategy and regime.

## 20.2 Required segmentation

```text
strategy
market_state
direction
symbol_behavior_group
liquidity_bucket
volatility_bucket
entry_type
confirmation_policy
timeframe_combination
broad_market_state
session_or_time_bucket_if relevant
```

## 20.3 Required metrics

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
liquidation_rate
fee_and_slippage_drag
```

## 20.4 Validation requirements

- chronological replay;
- no look-ahead leakage;
- production-equivalent feature calculation;
- active-candle rules reproduced exactly;
- realistic entry-touch assumptions;
- conservative same-candle stop/target ambiguity;
- fees, funding, spread, and slippage;
- changing historical symbol universe;
- delisted and failed symbols where data exists;
- train, validation, and untouched test periods;
- walk-forward evaluation;
- parameter stability checks;
- multiple-testing control;
- sensitivity tests around thresholds;
- long and short results separated;
- strategy/regime/symbol groups separated.

Success probability may only come from genuinely comparable out-of-sample setups. Otherwise output:

```text
Historical probability unavailable or insufficiently calibrated.
```

## 20.5 Research references to preserve in implementation notes

- Murphy, *Technical Analysis of the Financial Markets* — structure, trend, confirmation, volume/open interest, moving averages, oscillators, patterns.
- Nison, *Japanese Candlestick Charting Techniques* — candle completion, confluence, reversal warnings, trendlines, averages, oscillators, volume/open interest.
- Douglas, *Trading in the Zone* — uncertainty, predefined risk, consistency, sample-based edge.
- Liu and Tsyvinski, “Risks and Returns of Cryptocurrency,” *Review of Financial Studies* — crypto-specific predictors and time-series momentum.
- Han, Kang, and Ryu, “Momentum in the Cryptocurrency Market: A Comprehensive Analysis under Realistic Assumptions” — liquidation and tail-risk sensitivity; stronger time-series than cross-sectional evidence.
- Zaremba et al., “Up or down? Short-term reversal, momentum, and liquidity effects in cryptocurrency markets” — liquidity-dependent short-horizon behavior.
- Recent state-transition and survivorship studies must be considered before treating momentum rankings as stable edge.

---

# 21. Output reasoning

Every selected setup must explain:

## Why this coin

- discovery lane and rank;
- liquidity and spread;
- movement, volatility, and participation;
- market-state opportunity;
- broad-market relationship.

## Why this direction

- context-timeframe structure;
- setup-timeframe structure;
- local trigger;
- opposing evidence.

## Why this strategy

- compatible state;
- mandatory conditions;
- confirmation policy;
- why alternatives ranked lower.

## Why this entry

- zone construction;
- current-price relationship;
- preferred alternative;
- maximum chase;
- expiry.

## Why this stop

- invalidating structure;
- touch/wick/close rule;
- buffer;
- exact failure event.

## Why these targets

- source of each target;
- expected movement;
- R multiple;
- obstacles;
- condition for extensions.

## Why this duration

- timeframe roles;
- target distance;
- volatility;
- comparable historical timing.

## Why this confidence

- component scores;
- independent evidence families;
- historical segment if available;
- contradictions;
- missing data;
- rule-based or calibrated status.

---

# 22. Implementation sequence

## Phase 1 — Current pipeline audit

Map existing scan, analyze, screening, shortlisting, features, environment classification, strategies, entries, stops, targets, scoring, ranking, presentation, and backtesting. No behavior change.

## Phase 2 — Shared contracts and evidence taxonomy

Normalize market state, evidence family, contradiction, strategy candidate, entry opportunity, invalidation, target candidate, duration, confidence, and rejection contracts.

## Phase 3 — Discovery lanes

Implement separate trend, compression, fresh-break, fast-mover, range-rejection, and relative-strength lanes with one normalized shortlist contract.

## Phase 4 — Market usability and broad context

Implement execution filters, BTC/ETH context, breadth, correlation, and dispersion features without hard-coding broad context as universal rejection.

## Phase 5 — Multi-timeframe structure and market state

Implement deterministic structural map and primary/secondary state classifier.

## Phase 6 — Indicator evidence layer

Implement representative EMA/VWAP, RSI, MACD, volume, ATR, Bollinger-width, candle, and optional derivatives evidence with redundancy groups.

## Phase 7 — Strategy eligibility matrix

Make each strategy declare states, mandatory evidence, optional evidence, confirmation, blockers, penalties, entries, invalidation, targets, and expiry.

## Phase 8 — Multi-entry search and chase control

Support immediate, aggressive, preferred, pullback, retest, reclaim, rejection, and future-trigger entries.

## Phase 9 — Stop, liquidation, and risk geometry

Separate thesis invalidation, stop, volatility buffer, execution cost, position size, margin, liquidation estimate, and liquidation safety buffer.

## Phase 10 — Structural target and duration engine

Generate target candidates, movement envelopes, conditional extensions, expected holding range, and setup expiry.

## Phase 11 — Scoring, confidence, and ranking

Implement component scores, explicit gates, redundancy caps, contradictions, candidate comparison, and rule-based confidence.

## Phase 12 — Production-equivalent backtest and calibration

Run chronological tests, realistic costs, universe reconstruction, walk-forward validation, strategy/regime segmentation, and trade-suppression analysis.

## Phase 13 — Output upgrade

Update text and JSON while preserving CLI stability and deterministic serialization.

No implementation phase may claim validated profitability until the relevant local test and untouched historical evaluation outputs are provided.

---

# 23. Non-goals

The upgrade must not:

- guarantee winning trades;
- force a minimum number of results;
- force every target to 10%;
- force every trade into a short holding window;
- use leveraged return as expected market movement;
- display uncalibrated percentages as win probability;
- create candle-only strategies without context;
- treat oscillator extremes as automatic reversal trades;
- count correlated indicators repeatedly;
- add undocumented discretionary rules;
- redesign the repository;
- create separate analysis logic for scan and analyze;
- fabricate unavailable order-flow, open-interest, or liquidation data;
- optimize only for win rate, trade count, or headline return.

---

# 24. Definition of success

The methodology succeeds when Apex can consistently and reproducibly answer:

```text
Why this coin?
Why this direction?
Why this market state?
Why this strategy?
Which indicators matter, and what role does each play?
Why now?
Why this entry zone?
Is current price valid, aggressive, late, or missed?
Is there a better nearby entry?
Why this invalidation and stop?
Why these targets?
Why could movement reach 3%, 5%, 10%, or more?
How long may the setup remain valid?
What is the confidence level?
Is confidence rule-based or historically calibrated?
Which independent evidence matters most?
What contradicts the trade?
Why was another candidate ranked lower or rejected?
```

The final system should identify objectively defined opportunities with compatible market conditions, strategy-specific confirmation, fresh entry geometry, controlled structural risk, realistic target room, explicit uncertainty, transparent indicator roles, and evidence that survives realistic out-of-sample testing.
