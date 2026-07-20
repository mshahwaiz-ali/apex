# Apex Trading Project
## Multi-Opportunity, CMP-First Trade Discovery — Safe Implementation Plan

> **Status:** Planning and architecture document only  
> **Implementation policy:** No code changes, commits, pushes, or threshold tuning until the relevant inspection and acceptance gates are complete.  
> **Primary objective:** Make Apex expose the best structurally valid opportunities without confusing “not executable at CMP” with “no useful setup exists.”

---

## 1. Product Decision

Apex will no longer force every symbol into one global winning candidate.

For each analyzed symbol, the engine may return a small portfolio of distinct opportunities:

1. **Primary CMP trade**
2. **Best nearby limit setup**
3. **Best opposite-direction follow-up setup**
4. **Runner continuation or post-TP management plan**

The system remains **CMP-first**, but it must preserve valid nearby and sequential opportunities.

### Locked product rule

Apex must always expose the best structurally valid setup it found, including:

- direction;
- strategy family;
- actionability state;
- entry zone;
- ideal entry;
- maximum chase boundary;
- structural invalidation;
- executable stop;
- TP1, TP2, and TP3;
- activation conditions;
- early-failure conditions;
- runner conditions;
- supporting evidence;
- contradictions;
- score breakdown;
- historical calibration status when available.

Apex must never convert:

> “No safe CMP entry exists”

into:

> “No useful setup exists.”

---

## 2. Non-Negotiable Engineering Constraints

### 2.1 Shared analysis core

`apex scan` and `apex analyze SYMBOL` must use the same trade-analysis engine.

The commands may differ only in:

- symbol selection;
- requested analysis depth;
- opportunity count limits;
- presentation detail;
- optional diagnostic verbosity.

They must not maintain separate strategy logic, thresholds, stop logic, or scoring behavior.

### 2.2 Deterministic behavior

Given the same:

- market snapshot;
- configuration;
- symbol metadata;
- account/risk inputs;
- analysis mode;

Apex must return the same opportunity portfolio and ranking.

No display-layer code may silently alter selection.

### 2.3 No fabricated confidence

Apex must not claim 80%, 90%, or any other live accuracy unless that figure is supported by a sufficiently large out-of-sample sample for the same:

- strategy family;
- market regime;
- timeframe profile;
- execution state;
- fee/slippage model;
- symbol or liquidity class.

When calibration data is absent, output:

> Historical reliability: Uncalibrated

### 2.4 No threshold tuning before outcome audit

The initial implementation must not begin by loosening entry filters merely to increase displayed trades.

First determine whether the existing failures came from:

- weak setup selection;
- poor entry location;
- chasing;
- over-tight stops;
- incorrect target geometry;
- wrong regime routing;
- strategy collision;
- missing or stale market evidence;
- state-classification errors;
- presentation hiding valid alternatives.

### 2.5 Preserve working architecture

This is a focused redesign of the opportunity, selection, actionability, risk-geometry, lifecycle, and output contracts.

It is not permission to rebuild the repository from scratch.

---

## 3. Final Product Model

## 3.1 Opportunity slots per symbol

The symbol-level result should support the following conceptual slots:

| Slot | Purpose | Maximum normal count |
|---|---|---:|
| Current long | Best valid long at or extremely near CMP | 1 |
| Current short | Best valid short at or extremely near CMP | 1 |
| Nearby long | Best valid long limit/retest/reclaim opportunity | 1 |
| Nearby short | Best valid short limit/retest/reclaim opportunity | 1 |
| Follow-up opportunities | Structurally separate sequential/reversal plans | Configurable, normally 0–2 |
| Runner plan | Management of an already activated or TP1-reached trade | 0–1 |

These are slots, not mandatory outputs. Apex must not force-fill them.

### 3.2 Opportunity categories

#### Priority A — CMP opportunities

- `EXECUTE_NOW`
- `AGGRESSIVE_NOW`
- `EXECUTE_ON_MICRO_CONFIRMATION`

#### Priority B — Nearby opportunities

- `PLACE_LIMIT`
- `PLACE_LIMIT_WITH_ACTIVATION`
- `RETEST_PREFERRED`
- `RECLAIM_REQUIRED`

#### Priority C — Follow-up opportunities

Examples:

- sweep reversal;
- failed-breakout reversal;
- post-TP continuation;
- opposite reclaim;
- second-leg pullback;
- exhaustion recovery.

#### Priority D — Developing opportunities

- `DEVELOPING`

A developing setup remains visible only when it is structurally defined and not merely speculative.

---

## 4. Canonical Domain Contracts

The first implementation objective is a correct, typed domain contract. Strategy rewrites come later.

## 4.1 `TradeOpportunity`

Every opportunity should contain equivalent fields to the following conceptual model:

```text
identity
- opportunity_id
- symbol
- direction
- strategy_family
- setup_variant
- horizon
- sequence_role

state
- actionability_state
- maturity_state
- validation_state
- collision_state

market geometry
- cmp
- entry_zone_low
- entry_zone_high
- ideal_entry
- maximum_chase
- missed_entry_price
- structural_invalidation
- execution_stop
- stop_buffer
- stop_buffer_reason

activation
- activation_conditions
- confirmation_timeframe
- expiry_condition
- early_failure_conditions
- do_not_enter_conditions

targets
- tp1
- tp2
- tp3
- target_roles
- target_reasons
- initial_rr
- tp2_rr
- runner_rr

classification
- aligned_or_countertrend
- market_regime
- volatility_regime
- liquidity_class
- data_quality

scores
- setup_quality
- execution_quality
- continuation_quality
- contradiction_penalty
- data_quality_score
- historical_reliability

evidence
- required_evidence
- supporting_evidence
- contradictions
- missing_evidence

lifecycle
- runner_decision
- runner_hold_conditions
- runner_tighten_conditions
- runner_exit_conditions
```

### Contract rules

- Entry zones must be directional and ordered correctly.
- Stop must lie beyond structural invalidation after applying the execution buffer.
- Maximum chase must never improve the apparent reward-to-risk artificially.
- TP ordering must be valid for the direction.
- A complete setup must include at least one defensible target.
- `EXECUTE_NOW` is invalid when CMP is outside the executable entry region.
- `DEVELOPING` cannot be ranked above a valid current or nearby setup merely because its projected RR is larger.
- Historical reliability must include sample size and regime, or explicitly report uncalibrated status.

## 4.2 `SymbolOpportunityPortfolio`

```text
symbol
cmp
analysis_timestamp
market_snapshot_id
analysis_mode

current_long
current_short
nearby_long
nearby_short
follow_up_opportunities
runner_plan

collision_summary
rejection_summary
data_quality_summary
```

### Portfolio invariants

- Current long and current short may both exist.
- Both cannot be labelled high-confidence immediate executions in the same price area without an explicit collision result.
- Nearby and follow-up setups must be structurally distinct from current setups.
- Duplicate strategy variants must be merged or one must be rejected with a recorded reason.
- The portfolio must preserve rejected-candidate diagnostics under explain/debug mode.

## 4.3 Analysis modes

### `SCAN_CMP_FIRST`

Purpose:

- analyze a shortlisted universe;
- prioritize current and near-current scalps;
- retain concise valid alternatives;
- limit expensive diagnostics where safe;
- produce compact ranking and rejection summaries.

### `ANALYZE_FULL`

Purpose:

- deeply inspect one symbol;
- return current, nearby, opposite, and developing opportunities;
- explain timeframe alignment;
- expose stop/target/chase rationale;
- include evidence, contradictions, collisions, and lifecycle analysis;
- support raw diagnostics through `--explain`.

The strategy engine must not change its definition of a valid setup based on display mode. Mode may control breadth and explanation depth, not truth.

---

## 5. Actionability State Model

## 5.1 Final states

- `EXECUTE_NOW`
- `AGGRESSIVE_NOW`
- `EXECUTE_ON_MICRO_CONFIRMATION`
- `PLACE_LIMIT`
- `PLACE_LIMIT_WITH_ACTIVATION`
- `CMP_AVAILABLE_BUT_POOR_LOCATION`
- `RETEST_PREFERRED`
- `RECLAIM_REQUIRED`
- `MISSED_OR_CHASING`
- `DEVELOPING`
- `INVALIDATED`

`NO_CMP_ENTRY` may remain as a CMP assessment, but it must not replace the underlying setup state.

## 5.2 Required semantics

### `EXECUTE_NOW`

Use only when:

- CMP lies inside the executable entry zone;
- activation conditions are already satisfied;
- the setup is not stale;
- reward compression remains acceptable;
- spread and data freshness are acceptable;
- no unresolved directional collision exists.

### `AGGRESSIVE_NOW`

Use when:

- CMP entry is technically available;
- one or more confirmation elements remain incomplete;
- the output includes both aggressive and safer execution plans;
- the risk of incomplete confirmation is explicit.

This state must not be a euphemism for a weak setup.

### `EXECUTE_ON_MICRO_CONFIRMATION`

Use when:

- CMP location is still acceptable;
- a precise 1m/3m event can activate the entry;
- the event is objective and machine-checkable;
- the trigger has not already occurred and expired.

### `CMP_AVAILABLE_BUT_POOR_LOCATION`

Use when:

- directional thesis remains valid;
- CMP offers poor reward-to-risk, excessive chase, or proximity to opposing structure;
- a better limit or retest entry exists.

### `PLACE_LIMIT`

Use only when the limit zone is structurally valid without requiring a separate event beyond the normal hold condition.

### `PLACE_LIMIT_WITH_ACTIVATION`

Use when reaching the zone alone is insufficient and an objective reclaim, rejection, retest hold, or flow condition is required.

### `MISSED_OR_CHASING`

Use when:

- CMP crossed the maximum chase boundary;
- the original setup remains historically visible;
- the engine searches for a fresh continuation/retest setup instead of moving the old entry.

### `DEVELOPING`

Use when:

- the setup has a defined zone, invalidation, and activation path;
- it is not yet close enough or mature enough to execute;
- the plan has a meaningful expiry condition.

### `INVALIDATED`

Use when the structural thesis is already false. Do not continue showing executable prices from the invalidated plan.

---

## 6. Timeframe Responsibility Model

| Role | Timeframes | Responsibility |
|---|---|---|
| Market risk | 4h | Broad trend, extreme extension, major liquidity and structural levels |
| Context | 1h / 30m | Directional room, opposing structure, regime and continuation potential |
| Setup | 15m / 5m | Pattern, breakout, sweep, pullback, rejection, range structure |
| Activation | 3m | Local confirmation, reclaim/retest acceptance, micro structure |
| Timing | 1m | Precise entry timing, chase control, immediate momentum failure |

### 6.1 Higher-timeframe rule

The 4h direction is not an automatic entry veto.

#### Aligned continuation scalp

Effects may include:

- normal execution score;
- broader TP2/TP3 potential;
- more permissive runner retention;
- normal confirmation burden.

#### Countertrend scalp

Effects must include:

- explicit classification;
- lower continuation expectations;
- stronger activation requirement;
- TP1 treated as the primary objective;
- stricter runner conditions;
- stronger contradiction penalty;
- no automatic rejection when local geometry is strong.

The exact penalties must be configuration-driven and validated, not guessed.

---

## 7. Strategy Archetype Framework

Each archetype must implement the same interface and return candidates, not final global winners.

Every archetype must define:

- required evidence;
- optional supporting evidence;
- contradictions;
- invalidation logic;
- CMP entry logic;
- nearby-entry logic;
- activation conditions;
- stop logic;
- target logic;
- maximum-chase logic;
- missed-entry handling;
- runner rules;
- regime suitability;
- data requirements;
- explanation labels.

## 7.1 Momentum breakout scalp

Required concepts:

- genuine structural break;
- compression or prior balance;
- relative-volume expansion;
- acceptable extension;
- target room;
- micro flow or acceptance support.

Must produce, where valid:

- CMP breakout entry;
- retest limit alternative;
- maximum chase;
- failure/re-entry condition.

Must reject:

- late extended candles;
- breakouts directly into opposing liquidity;
- poor spread or insufficient volume;
- breakouts without acceptance.

## 7.2 First pullback after expansion

Must distinguish:

- healthy pullback;
- deep but recoverable pullback;
- failed continuation.

Useful evidence:

- impulse strength;
- retracement depth;
- pullback volume decay;
- VWAP/EMA/broken-level hold;
- 3m structure preservation;
- renewed aggression.

## 7.3 Breakout retest

Must define:

- original breakout level;
- retest zone;
- acceptable penetration;
- hold/rejection requirement;
- structural invalidation;
- target space.

This archetype is the primary source of early planned limit orders.

## 7.4 VWAP reclaim/rejection

Must avoid treating every VWAP cross as a signal.

Require context such as:

- prior sweep or displacement;
- acceptance duration;
- local structure change;
- flow support;
- sufficient room to target.

## 7.5 Liquidity sweep reversal

Must define:

- swept reference level;
- sweep magnitude;
- close/reclaim behavior;
- absorption or momentum failure;
- entry on rejection or retest;
- invalidation beyond sweep extreme plus buffer.

Top-gainer and top-loser use requires stricter confirmation.

## 7.6 Failed-breakout reversal

Must detect:

- attempted break;
- lack of sustained acceptance;
- return inside prior structure;
- trapped-side evidence;
- local structure flip.

The initial breakout plan and later failed-breakout reversal may both exist if their sequence is coherent.

## 7.7 Compression expansion

Before activation, the engine may preserve both conditional directions when both sides remain structurally possible.

After activation, the non-activated side must be re-evaluated, not automatically carried forward.

## 7.8 Exhaustion scalp

Must not be based on RSI overbought/oversold alone.

Potential evidence:

- extreme extension;
- weakening momentum;
- failed marginal high/low;
- rejection wick quality;
- taker-flow deceleration;
- price/open-interest divergence;
- liquidation impulse;
- reclaim or local structure flip.

---

## 8. Opportunity Generation Pipeline

The engine should use an explicit staged pipeline.

### Stage 1 — Market snapshot validation

Validate:

- required timeframes present;
- candle freshness;
- symbol precision metadata;
- spread availability;
- indicator readiness;
- no malformed or duplicated candles;
- optional evidence availability;
- snapshot timestamp consistency.

If critical data is stale or absent, reduce data-quality score or reject states that require live evidence.

### Stage 2 — Context derivation

Derive once per symbol:

- multi-timeframe structure;
- volatility regime;
- trend/alignment map;
- nearby liquidity;
- major opposing levels;
- spread/liquidity class;
- extension state;
- data-quality summary.

Strategies must consume the same context object rather than recomputing inconsistent versions.

### Stage 3 — Strategy candidate generation

Each enabled strategy family independently returns zero or more raw candidates.

No strategy chooses the final opportunity portfolio.

### Stage 4 — Geometry normalization

For every raw candidate:

- normalize direction;
- build entry zone;
- calculate ideal entry;
- calculate maximum chase;
- determine structural invalidation;
- apply noise/spread/ATR buffer;
- generate TP1–TP3;
- compute RR values;
- define activation and early-failure conditions.

### Stage 5 — Candidate validation

Reject or downgrade candidates with:

- invalid directional geometry;
- missing structural stop;
- no target room;
- unacceptable spread;
- stale activation;
- contradictory state;
- insufficient required evidence;
- already-breached invalidation;
- impossible precision rounding;
- chase boundary already exceeded.

### Stage 6 — Actionability classification

Classify from objective geometry and trigger state.

This stage must not use CLI wording or visual priority.

### Stage 7 — Scoring

Generate separate scores for:

- setup quality;
- execution quality;
- continuation quality;
- historical reliability;
- data quality.

Do not collapse all dimensions into one opaque number before portfolio selection.

### Stage 8 — Deduplication

Merge or reject candidates that share substantially the same:

- direction;
- strategy family;
- entry region;
- invalidation;
- activation event;
- target path.

Keep the stronger explanation and preserve contributing evidence.

### Stage 9 — Collision resolution

Evaluate:

- same-direction overlap;
- opposite-direction CMP collision;
- sequential opposite setups;
- activation-order conflicts;
- stop/trigger interaction.

### Stage 10 — Portfolio selection

Select separately:

- best current long;
- best current short;
- best nearby long;
- best nearby short;
- valid follow-up opportunities.

Do not select one global winner before these categories are filled.

### Stage 11 — Mode filtering

Apply scan/analyze breadth limits without changing validity.

### Stage 12 — Presentation mapping

CLI rendering consumes the final portfolio. It must not recompute states, RR, ranking, or rejection reasons.

---

## 9. Stop-Loss Architecture

Stops must be structural, not fixed arbitrary percentages.

## 9.1 Stop components

### Structural invalidation

The price where the thesis becomes objectively false, such as:

- sweep extreme;
- failed-breakout boundary;
- pullback structure low/high;
- reclaimed-level failure;
- range boundary;
- compression failure boundary.

### Execution buffer

A configurable buffer beyond structural invalidation based on relevant components:

- ATR fraction;
- spread allowance;
- tick size;
- local wick/noise profile;
- volatility regime;
- strategy-specific minimum buffer.

### Executable stop

The actual stop after symbol precision normalization.

## 9.2 Required outputs

- structural invalidation price;
- execution stop price;
- total buffer;
- reason for buffer;
- stop distance percentage;
- stop distance in ATR units;
- early-failure conditions.

## 9.3 Safety checks

Reject or downgrade when:

- stop falls inside normal noise;
- stop distance destroys feasible position sizing;
- stop lies beyond a major unrelated structure;
- target path cannot support acceptable expectancy;
- precision rounding moves stop to the wrong side of invalidation.

---

## 10. Target Architecture

Targets must be selected from defensible market structure.

### TP1 — Scalp realization

Normally based on:

- nearest local liquidity;
- previous high/low;
- range boundary;
- first meaningful opposing structure;
- minimum acceptable RR subject to expectancy.

### TP2 — Intraday continuation

Normally based on:

- next significant liquidity zone;
- next intraday structural objective;
- measured continuation supported by room and volatility.

### TP3 — Runner target

Normally based on:

- higher-timeframe liquidity;
- larger measured move;
- regime-supported continuation objective.

### Required target metadata

For each target:

- price;
- role;
- source structure;
- RR from ideal entry;
- distance from CMP;
- quality/probability band when calibrated;
- conditions required to retain the target.

Apex does not decide the user’s amount allocation across targets.

---

## 11. Chase and Missed-Entry Architecture

Every executable opportunity must include:

- ideal entry;
- executable entry zone;
- maximum chase;
- missed-entry price;
- do-not-enter rule.

### Long example semantics

- entry zone: acceptable purchase area;
- maximum chase: highest acceptable entry before reward compression becomes unacceptable;
- missed-entry price: point where the original execution plan is no longer valid;
- above that level: mark `MISSED_OR_CHASING` and search for a fresh retest or continuation setup.

### Short example semantics

The boundaries are directionally inverted.

### Critical invariant

The engine must never move an old entry zone to CMP merely to keep a signal executable.

---

## 12. Opposite Setups and Collision Handling

## 12.1 Sequential opposite setups

Both directions may remain valid when:

- activation zones are structurally separate;
- activation order is understandable;
- the first setup is likely to complete, fail, or invalidate before the second activates;
- each has independent invalidation;
- each has distinct evidence;
- the second is not merely a mirrored guess.

Example:

- current short scalp;
- lower-price long sweep recovery.

## 12.2 Unresolved CMP collision

When both long and short are executable in the same area and score difference is insufficient:

- mark directional collision;
- reduce execution confidence;
- display both plans;
- require a defined micro trigger;
- do not label either as high-confidence `EXECUTE_NOW`.

### Suggested collision object

```text
collision_type
long_opportunity_id
short_opportunity_id
score_difference
entry_overlap
trigger_conflict
resolution
preferred_micro_trigger
```

## 12.3 Same-direction duplicates

Near-identical setups from multiple strategies must not create noisy cards.

Choose one of:

- merge evidence into the stronger candidate;
- retain the structurally superior candidate;
- retain both only if activation or horizon is materially different.

---

## 13. Scoring Model

## 13.1 Separate score dimensions

### Setup quality

Measures:

- structural location;
- pattern integrity;
- regime suitability;
- target room;
- contradiction burden;
- required-evidence completeness.

### Execution quality

Measures:

- CMP/entry-zone relationship;
- chase risk;
- spread;
- activation maturity;
- stop efficiency;
- microstructure confirmation;
- data freshness.

### Continuation quality

Measures:

- higher-timeframe room;
- alignment;
- volume/flow persistence;
- opposing liquidity;
- runner feasibility;
- trend maturity.

### Historical reliability

Must include:

- win rate or TP1 rate;
- expectancy;
- sample size;
- strategy;
- regime;
- confidence interval or uncertainty indicator where feasible;
- calibration period;
- fee/slippage assumptions.

### Data quality

Measures:

- freshness;
- completeness;
- synchronization;
- missing optional/required feeds;
- spread reliability;
- order-book reliability.

## 13.2 Scoring safeguards

- Required evidence failures cannot be fully offset by optional indicators.
- Data-quality degradation must cap execution confidence.
- Countertrend classification affects continuation more than setup existence.
- A large projected RR cannot rescue invalid entry geometry.
- Historical reliability cannot be merged into current setup quality without preserving sample information.
- Score weights must be configuration-driven and covered by tests.

---

## 14. Runner and Post-TP Lifecycle

After TP1, Apex should classify the remaining position into one of:

- `HOLD_RUNNER`
- `TIGHTEN_AND_HOLD`
- `EXIT_REMAINDER`

## 14.1 `HOLD_RUNNER`

Typical requirements:

- 3m and 5m structure intact;
- no opposite reclaim;
- continuation volume remains healthy;
- correct side of VWAP/EMA maintained;
- target room remains;
- no strong opposing absorption;
- 15m thesis remains valid.

## 14.2 `TIGHTEN_AND_HOLD`

Use when:

- core structure remains intact;
- momentum is slowing;
- opposing structure is approaching;
- flow is becoming mixed;
- profit protection is warranted.

The output must identify the exact protect level or structural trailing reference.

## 14.3 `EXIT_REMAINDER`

Use when:

- opposite reclaim occurs;
- 3m structure breaks;
- continuation fails;
- volume climax and rejection appear;
- price/OI behavior implies squeeze risk;
- momentum reversal is confirmed;
- time-based stagnation invalidates the continuation thesis.

## 14.4 Original thesis comparison

A rerun of `apex analyze SYMBOL` should be able to compare:

- original setup state;
- original entry and invalidation;
- achieved targets;
- current structure;
- current runner decision;
- changed evidence;
- new contradictions.

This comparison should use a stable setup identifier or persisted trade-plan snapshot when available.

---

## 15. Market Data Strategy

Before adding feeds, inspect what is:

- fully implemented;
- partially implemented;
- declared but unused;
- fetched but not included in decisions;
- available only in diagnostics;
- stale or incorrectly synchronized.

## 15.1 High-value static evidence

- multi-timeframe klines;
- mark and ticker price;
- 24h volume;
- spread;
- funding;
- open-interest history;
- taker buy/sell volume;
- premium/mark relationship;
- order-book snapshot.

## 15.2 High-value live activation evidence

- aggregate trades;
- best bid/ask;
- synchronized depth updates;
- current candle updates;
- reliable liquidation/forced-order data when officially available and stable.

## 15.3 Derived features

Potential additions, only where they improve a decision:

- cumulative taker imbalance;
- aggression acceleration;
- order-book imbalance;
- spread deterioration;
- liquidity-wall proximity;
- open-interest expansion/contraction;
- price/OI relationship;
- funding crowding;
- liquidation impulse;
- volume-delta approximation;
- breakout acceptance duration;
- retest depth;
- pullback volume ratio.

## 15.4 Data safeguards

- Order-book walls are supporting evidence, not core truth.
- Live data sequence gaps must invalidate or degrade depth-derived evidence.
- REST and WebSocket timestamps must be normalized.
- Required and optional evidence must be explicit per strategy.
- Absence of optional evidence must not be presented as negative evidence.
- Stale live inputs must not activate `EXECUTE_NOW`.

---

# 16. Safe Big-Batch Implementation Roadmap

The work is divided into large, coherent batches. Each batch has a locked scope, tests, and an exit gate. No batch should mix broad contract changes with cosmetic CLI redesign.

---

## Batch 0 — Repository and Behavior Audit

### Goal

Establish the true current architecture and capture baseline behavior before changes.

### Work

1. Map the complete flow for:
   - `apex scan`;
   - `apex analyze SYMBOL`;
   - symbol shortlisting;
   - market-data acquisition;
   - feature generation;
   - strategy routing;
   - actionability classification;
   - stop/target calculation;
   - candidate ranking;
   - CLI rendering.
2. Identify duplicated scan/analyze logic.
3. Identify all current candidate and result contracts.
4. Locate every place that:
   - discards non-winning candidates;
   - changes states;
   - clamps or rewrites entries;
   - calculates stops or targets;
   - computes confidence;
   - hides rejected setups;
   - formats CLI output.
5. Inspect configuration keys and defaults.
6. Inventory current tests and missing coverage.
7. Record current live or fixture-based outputs without claiming validity.
8. Inspect whether the previously reported losing trades are stored.

### Deliverables

- architecture map;
- current-behavior matrix;
- contract inventory;
- duplication report;
- data-source wiring report;
- regression-risk list;
- proposed file-by-file change map.

### Exit gate

Do not begin contract changes until the shared-core boundary and current single-winner selection path are identified.

---

## Batch 1 — Outcome Audit and Failure Taxonomy

### Goal

Understand why recent trades failed before changing thresholds.

### Work

For each available losing or invalid trade, record:

- symbol;
- timestamp;
- strategy;
- direction;
- market regime;
- CMP/limit state;
- intended entry;
- actual entry if known;
- entry distance from ideal;
- maximum chase state;
- structural invalidation;
- executable stop;
- stop distance;
- MFE;
- MAE;
- TP1/TP2/TP3 result;
- higher-timeframe relationship;
- volume, OI, taker-flow state;
- data-quality state;
- collision state;
- final failure category.

### Failure taxonomy

- bad setup;
- bad entry;
- chased entry;
- stop too tight;
- invalid stop location;
- wrong target;
- insufficient target room;
- regime mismatch;
- strategy collision;
- stale/missing data;
- wrong state classification;
- valid setup but normal loss;
- execution mismatch between Apex output and actual trade.

### Deliverables

- outcome-audit table;
- failure distribution;
- MFE/MAE summary;
- threshold-change recommendations, if supported;
- list of problems that are contract/presentation issues rather than strategy issues.

### Exit gate

No broad threshold relaxation without evidence from this audit.

---

## Batch 2 — New Domain Contracts and Compatibility Layer

### Goal

Introduce the opportunity portfolio model without changing strategy behavior yet.

### Work

1. Add typed contracts for:
   - trade opportunity;
   - target plan;
   - stop plan;
   - activation plan;
   - score breakdown;
   - evidence set;
   - collision result;
   - symbol opportunity portfolio;
   - analysis mode.
2. Add strict invariants and validation.
3. Build an adapter from current single-candidate output into the new portfolio.
4. Preserve existing public behavior behind a temporary compatibility mapping where necessary.
5. Add serialization snapshots for debugging and tests.

### Tests

- directional price geometry;
- stop/invalidation ordering;
- TP ordering;
- maximum chase ordering;
- state/entry consistency;
- optional historical reliability;
- portfolio slot uniqueness;
- serialization stability.

### Exit gate

The repository must compile and tests must prove that existing behavior can be represented in the new contract before strategy selection is changed.

---

## Batch 3 — Shared Analysis Orchestrator

### Goal

Make scan and analyze use one orchestration path.

### Work

1. Create or consolidate a shared symbol-analysis service.
2. Centralize:
   - snapshot validation;
   - context derivation;
   - strategy invocation;
   - candidate normalization;
   - validation;
   - actionability;
   - scoring;
   - deduplication;
   - collision handling;
   - portfolio selection.
3. Implement analysis modes as parameters.
4. Keep CLI presentation outside the domain/application decision path.
5. Remove or deprecate duplicated command-specific logic only after parity tests pass.

### Tests

- same symbol/snapshot/config produces the same underlying opportunities in scan and analyze;
- mode changes breadth/detail but not validity;
- deterministic ordering;
- no CLI dependency in strategy code;
- no strategy-specific branching in command handlers.

### Exit gate

A parity suite must show that scan and analyze consume the same engine.

---

## Batch 4 — Multi-Candidate Generation and Portfolio Selection

### Goal

Stop discarding useful long, short, nearby, and follow-up candidates.

### Work

1. Change strategy routing to emit candidate collections.
2. Preserve candidate origin and evidence.
3. Classify candidates into current, nearby, follow-up, or developing groups.
4. Implement separate ranking for:
   - current long;
   - current short;
   - nearby long;
   - nearby short.
5. Implement near-duplicate merging.
6. Implement sequential-opportunity checks.
7. Keep rejected candidates and reasons for explain mode.

### Ranking precedence

Within each slot, use a deterministic sequence such as:

1. validation state;
2. actionability tier;
3. execution quality;
4. setup quality;
5. contradiction burden;
6. target-room sufficiency;
7. continuation quality;
8. data quality;
9. historical reliability where calibrated;
10. stable tie-breaker.

Exact order should be confirmed against current architecture and tests.

### Exit gate

Fixtures must demonstrate that a valid nearby or opposite sequential setup is retained even when a CMP candidate exists.

---

## Batch 5 — Actionability and Chase Rewrite

### Goal

Make every state objectively tied to entry geometry and activation maturity.

### Work

1. Implement final states.
2. Define state precedence.
3. Separate CMP assessment from setup existence.
4. Add ideal entry, maximum chase, and missed-entry boundaries.
5. Add machine-checkable micro-confirmation triggers.
6. Mark stale or expired triggers.
7. Search for a fresh setup after a missed entry instead of moving the old entry.

### Required scenario tests

- CMP inside valid zone and trigger complete;
- CMP inside zone but confirmation incomplete;
- CMP near zone with objective trigger;
- CMP beyond chase boundary;
- valid limit setup but no CMP entry;
- invalidated setup;
- stale micro-confirmation;
- contradictory immediate long and short.

### Exit gate

No state may be assigned solely from a score threshold without validating price geometry and trigger state.

---

## Batch 6 — Strategy Archetype Hardening

### Goal

Convert strategy families to the common archetype contract.

### Suggested implementation order

1. existing strongest continuation strategy;
2. breakout retest;
3. first pullback;
4. VWAP reclaim/rejection;
5. liquidity sweep;
6. failed breakout;
7. compression expansion;
8. exhaustion reversal.

### Why staged inside one batch

Each archetype should be migrated independently behind focused tests, but the batch is complete only when routing and outputs are consistent.

### Work per archetype

- required evidence;
- optional evidence;
- contradictions;
- regime eligibility;
- candidate variants;
- CMP logic;
- nearby logic;
- activation;
- structural stop;
- target sources;
- chase boundary;
- runner logic;
- explanation labels.

### Exit gate

No archetype may bypass the shared geometry, actionability, scoring, deduplication, or collision pipeline.

---

## Batch 7 — Dynamic Stop, Target, and Risk Geometry

### Goal

Replace arbitrary or generic geometry with strategy-aware structural planning.

### Work

1. Build reusable structural invalidation service.
2. Build volatility/spread/noise buffer service.
3. Build target-source resolver.
4. Calculate TP1–TP3 and RR from the same entry assumptions.
5. Add early-failure conditions.
6. Integrate symbol precision and tick-size rounding.
7. Ensure compatibility with account-aware sizing and leverage logic.
8. Prevent impossible plans where stop geometry and account risk cannot coexist.

### Tests

- long and short symmetry;
- structural boundary selection;
- buffer behavior by volatility regime;
- precision rounding;
- target ordering;
- no target room;
- poor RR after chase;
- countertrend target compression;
- account risk compatibility.

### Exit gate

Every displayed complete setup must have defensible and internally consistent entry, stop, target, and chase geometry.

---

## Batch 8 — Collision, Sequence, and Lifecycle Engine

### Goal

Support coherent multi-opportunity sequences and post-TP decisions.

### Work

1. Implement CMP collision detection.
2. Implement score-difference and overlap rules.
3. Implement sequential opposite-setup validation.
4. Add opportunity expiry and invalidation transitions.
5. Add runner evaluator:
   - `HOLD_RUNNER`;
   - `TIGHTEN_AND_HOLD`;
   - `EXIT_REMAINDER`.
6. Add comparison with original plan where persistence exists.

### Tests

- current short followed by lower long sweep;
- current long and current short in same zone;
- first setup invalidation activates second;
- duplicate opposite setup without independent thesis;
- runner hold;
- runner tighten;
- runner exit;
- expired follow-up.

### Exit gate

The system must explain why two opposite opportunities can coexist or why they are in unresolved collision.

---

## Batch 9 — High-Value Data Evidence Expansion

### Goal

Add only data that materially improves activation, execution, or continuation decisions.

### Work

1. Audit existing implementation and actual usage.
2. Prioritize missing high-value evidence.
3. Add synchronization and freshness guards.
4. Derive features centrally.
5. Expose data quality to scoring.
6. Add graceful degradation when optional feeds fail.

### Priority order

1. reliable aggregate-trade imbalance;
2. price/open-interest relationship;
3. breakout acceptance duration;
4. pullback-volume decay;
5. spread deterioration;
6. depth imbalance only with correct synchronization;
7. liquidation impulse only when reliable.

### Exit gate

Every added feature must be tied to at least one explicit strategy or state decision and covered by tests. No feature dumping.

---

## Batch 10 — CLI Restoration and Information Architecture

### Goal

Restore rich trading information without allowing UI concerns to alter decisions.

### `apex scan` sections

1. Actionable at CMP
2. Nearby limit entries
3. Micro-confirmation entries
4. Follow-up/reversal setups
5. Weak or invalid setup summary

### Top-card minimum fields

- symbol and side;
- strategy;
- status;
- CMP;
- entry zone;
- ideal entry;
- maximum chase;
- stop;
- TP1–TP3;
- initial and runner RR;
- setup quality;
- execution quality;
- continuation quality;
- alignment/countertrend classification;
- concise evidence;
- main risk.

### Compact ranking minimum fields

- symbol;
- side;
- state;
- entry distance;
- setup score;
- execution score;
- TP1 RR;
- data-quality warning where relevant.

### `apex analyze SYMBOL` sections

1. Current opportunity
2. Nearby alternative
3. Opposite follow-up
4. Developing setups
5. Multi-timeframe map
6. Entry, stop, and target rationale
7. Chase boundary
8. Evidence and contradictions
9. Collision analysis
10. Runner/lifecycle decision
11. Rejected candidates under `--explain`
12. Data-quality diagnostics under `--explain`

### CLI safeguards

- Preserve complete numbers; do not hide risk geometry for visual compactness.
- Clearly distinguish no CMP entry from no valid setup.
- Clearly mark uncalibrated historical reliability.
- Never display an invalidated setup as executable.
- Do not silently truncate opportunities without a count/summary.

### Exit gate

Snapshot tests must confirm that essential trading data remains visible in both compact and detailed output.

---

## Batch 11 — Backtest, Calibration, and Acceptance Framework

### Goal

Validate precision and expectancy rather than maximizing signal count.

### Required metrics

- win rate;
- profit factor;
- expectancy;
- average R;
- TP1 hit rate;
- TP2 hit rate;
- runner success rate;
- stop rate;
- false CMP signal rate;
- MFE;
- MAE;
- performance by strategy;
- performance by regime;
- performance by confidence band;
- performance by actionability state;
- countertrend versus aligned performance;
- fees and slippage;
- liquidation or margin failure rate where relevant.

### Calibration rules

- chronological splits;
- no future leakage;
- realistic trigger handling;
- entry-zone and maximum-chase rules respected;
- fees and slippage included;
- partial targets modelled consistently;
- missed trades not counted as wins;
- stale/developing setups handled accurately;
- sample size always reported.

### Acceptance principle

A high TP1 rate is insufficient if stops are disproportionately large or expectancy is negative.

Acceptance requires:

> calibrated precision + positive expectancy + tolerable drawdown + stable regime performance

### Exit gate

No confidence-band claims become user-facing until calibration supports them.

---

## Batch 12 — Controlled Rollout and Cleanup

### Goal

Move safely from compatibility behavior to the new product model while keeping
the legacy path recoverable until diagnostic evidence supports removal.

### Controlled rollout sequence

1. Keep new contracts behind the compatibility adapter.
2. Exercise the shared orchestrator through deterministic tests.
3. Expose multi-opportunity results in non-authoritative diagnostic mode.
4. Compare legacy and portfolio projections on fixed fixtures.
5. Separate expected compatibility gaps from structural regressions.
6. Require zero structural regressions for diagnostic acceptance.
7. Keep rollout diagnostics disabled by default.
8. Allow operators to enable diagnostics through typed configuration.
9. Write dedicated rollout reports only when explicitly requested.
10. Enable new scan or analyze output only after reviewed evidence.
11. Remove obsolete single-winner paths only after parity and regression review.
12. Remove deprecated configuration only after migration documentation.

### Current controlled-rollout controls

```yaml
rollout_diagnostics_enabled: false
```

When disabled:

- normal scan and analyze payloads remain unchanged;
- no rollout comparison fields are attached;
- no rollout report can be written.

When enabled:

- diagnostics remain explicitly non-authoritative;
- scan and analyze use the same serialization switch;
- `--rollout-report PATH` writes a dedicated operator artifact;
- acceptance evaluation does not alter trade selection or command exit status.

### Evidence gate

Before enabling any new output as authoritative, review a fixed and reproducible
comparison set. The evidence must include:

- exact-match count;
- compatibility-only difference count;
- structural regression count;
- differences by field;
- affected fixture or symbol identities;
- representative generated report;
- Ruff, mypy, and focused pytest output;
- operator sign-off.

Diagnostic acceptance requires:

```text
regression_count == 0
```

Compatibility-only differences may be accepted when they are documented and do
not conceal changes to strategy, direction, geometry, targets, rejection
reasons, or opportunity count.

### Rollback boundary

Keep every major rollout step independently revertible. Do not combine:

- compatibility removal;
- strategy threshold tuning;
- live-data expansion;
- CLI redesign;
- calibration changes;
- authoritative-output activation

in one commit.

The immediate rollback control is:

```yaml
rollout_diagnostics_enabled: false
```

If an authoritative output is enabled later, rollback must restore the previous
serializer or adapter without reverting unrelated methodology work.

### Operator runbook

Use `docs/rollout_operations.md` for:

- enabling and disabling diagnostics;
- generating analyze and scan rollout reports;
- reviewing acceptance results;
- collecting validation evidence;
- rollback triggers;
- compatibility-removal prerequisites.

### Final cleanup gate

The following remain blocked until controlled-rollout evidence is approved:

- delete dead compatibility code;
- remove duplicate selectors;
- remove unused or deprecated configuration;
- make portfolio output authoritative;
- remove legacy single-winner serialization.

Documentation cleanup must also include:

- README command examples;
- command help;
- architecture diagrams;
- state semantics;
- calibration limitations;
- migration and rollback notes.

---

## 17. Configuration Design

All meaningful thresholds should be explicit and grouped by responsibility.

Suggested groups:

```text
analysis_modes
opportunity_portfolio
actionability
chase_control
collision_resolution
strategy_archetypes
stop_geometry
target_geometry
runner_lifecycle
scoring
data_quality
market_data
calibration
cli
```

### Configuration safeguards

- defaults must be documented;
- units must be explicit;
- percentages versus ratios must not be ambiguous;
- invalid combinations must fail validation;
- strategy-specific overrides must inherit cleanly;
- configuration changes must be represented in test fixtures;
- thresholds must not be scattered through command or rendering code.

---

## 18. Testing Strategy

## 18.1 Unit tests

Cover:

- contract invariants;
- geometry;
- state classification;
- score components;
- deduplication;
- collision logic;
- target selection;
- stop buffer;
- chase boundaries;
- runner decisions;
- data freshness.

## 18.2 Strategy fixture tests

Each archetype requires fixtures for:

- valid aligned setup;
- valid countertrend setup;
- valid CMP entry;
- valid nearby entry;
- missed/chased setup;
- invalidated setup;
- insufficient evidence;
- contradiction-heavy setup;
- no target room;
- stale data.

## 18.3 Integration tests

Cover:

- shared scan/analyze core;
- full portfolio generation;
- ranking and slot selection;
- CLI mapping;
- configuration loading;
- data-provider degradation;
- account-aware risk compatibility.

## 18.4 Regression tests

Capture:

- current known scan/analyze fixtures;
- reported losing-trade scenarios where reconstructable;
- single-candidate compatibility behavior;
- existing CLI contract expectations;
- symbol precision edge cases.

## 18.5 Property/invariant tests

Useful invariants:

- long stop below entry; short stop above entry;
- long TP ordering ascending; short TP ordering descending;
- maximum chase cannot improve RR versus ideal entry;
- invalidation cannot be crossed by an executable current state;
- `EXECUTE_NOW` requires CMP in zone;
- `MISSED_OR_CHASING` requires chase boundary breach;
- duplicate portfolio slots cannot reference the same opportunity;
- no NaN/inf scores or prices;
- rounding preserves directional safety.

---

## 19. Validation Workflow Per Batch

For every implementation batch:

1. Inspect current files before editing.
2. Limit changes to the batch scope.
3. Format changed files.
4. Run Ruff autofix safely.
5. Run Ruff check.
6. Run scoped mypy on changed modules and their direct contract consumers.
7. Run focused unit tests.
8. Run relevant integration tests.
9. Run CLI fixture/snapshot tests when presentation or orchestration changes.
10. Review `git diff --check`.
11. Review the complete diff for accidental behavior changes.
12. Record unvalidated areas explicitly.

Recommended command pattern after actual changed files are known:

```bash
.venv/bin/ruff format <changed-files>
.venv/bin/ruff check <changed-files> --fix
.venv/bin/ruff check <changed-files>
.venv/bin/mypy <scoped-modules>
.venv/bin/pytest <focused-tests>
git diff --check
```

Never claim validation passed without actual terminal output.

---

## 20. Definition of Done

The redesign is complete only when all of the following are true:

- scan and analyze share one decision engine;
- every symbol can expose distinct current, nearby, and follow-up opportunities;
- no global winner suppresses valid alternatives prematurely;
- actionability states are geometry- and trigger-driven;
- no-CMP-entry does not mean no setup;
- maximum chase and missed-entry handling are mandatory;
- stops are structurally derived with explicit buffers;
- TP1–TP3 are structurally justified;
- opposite setups have explicit collision or sequence logic;
- runner decisions are objective and explainable;
- scores remain separated by purpose;
- uncalibrated reliability is labelled honestly;
- data-quality limitations affect execution confidence;
- CLI output includes complete trade geometry;
- rejected candidates are inspectable under explain mode;
- backtests include fees, slippage, timing, partial exits, and no leakage;
- acceptance is based on expectancy and calibrated precision, not signal quantity;
- legacy single-winner paths and duplicate logic are removed after safe rollout.

---

## 21. Additional Improvements Added to the Original Specification

The following improvements strengthen the product beyond the initial plan:

### 21.1 Maturity and actionability are separate

A setup can be structurally strong but not mature. Keeping these dimensions separate prevents weak wording such as “high-quality execute now” when the trigger is incomplete.

### 21.2 Data-quality score and execution cap

A strong chart pattern with stale live data must not receive unrestricted execution confidence.

### 21.3 Opportunity expiry

Every conditional setup should define when it expires due to:

- time;
- structure change;
- volatility shift;
- target consumption;
- opposing activation;
- data staleness.

### 21.4 Stable opportunity identity

A stable identifier enables:

- lifecycle comparisons;
- trade journaling;
- post-TP analysis;
- backtest traceability;
- avoiding accidental duplication across reruns.

### 21.5 Rejection reason taxonomy

Rejected candidates should use machine-readable reasons, not free text only. This supports debugging and calibration.

### 21.6 Score caps instead of hidden rejection

Some weaknesses should cap a score or state rather than delete the setup, for example:

- countertrend context;
- partial live-data availability;
- incomplete continuation evidence.

Hard invalidation remains reserved for true structural or contract failures.

### 21.7 Execution-state expiry

`EXECUTE_ON_MICRO_CONFIRMATION` must expire after the relevant trigger window. Otherwise stale triggers can appear actionable long after market structure changes.

### 21.8 Explainability at every pipeline stage

Each final opportunity should be traceable through:

- strategy source;
- raw evidence;
- geometry decisions;
- state classification;
- score adjustments;
- deduplication;
- collision handling;
- portfolio selection.

### 21.9 Presentation must be a pure projection

CLI code should render domain results only. It must not decide which signal wins, recalculate RR, or change states.

### 21.10 Compare old and new engines before deletion

A fixed replay set should show where outputs changed and why. This prevents accidental improvements in one scenario from causing silent regressions elsewhere.

---

## 22. Recommended Immediate Next Step

Start with **Batch 0 only**.

The next working session should:

1. inspect the current repository from GitHub `main`;
2. map the scan and analyze call graphs;
3. identify the current single-winner choke point;
4. inventory domain models and state enums;
5. locate stop, target, scoring, and CLI logic;
6. inspect existing data-source wiring;
7. inspect tests;
8. produce a file-by-file implementation map for Batches 1–3.

No implementation should begin until that audit confirms the safest integration boundary.

---

## 23. Final Product Statement

Apex is a CMP-first, multi-opportunity futures trade-analysis system.

It should prioritize immediately actionable trades while preserving nearby limit entries, structurally independent opposite follow-ups, and post-TP continuation decisions. It must provide complete execution geometry, avoid chasing, distinguish setup quality from execution readiness, and remain honest about uncertainty and historical reliability.

The system’s objective is not to produce the maximum number of signals or claim unrealistic accuracy. Its objective is to produce the most defensible, explainable, and executable opportunities available from the current market evidence while controlling false positives and preserving positive expectancy after realistic costs.

### Batch 12 completion boundary

Batch 12 is complete when the final cleanup-readiness audit confirms:

- disabled-by-default behavior;
- explicit diagnostic opt-in;
- shared scan/analyze rollout wiring;
- non-authoritative acceptance;
- dedicated operator reporting;
- legacy compatibility retention;
- documented rollback and removal prerequisites.

Completion of Batch 12 does not itself remove compatibility code or activate
portfolio output as authoritative. Those actions remain blocked by the final
cleanup gate and require a separate reviewed change.
