# Apex Scalping and Runner Methodology Improvement Plan

## Status

- **Phase:** Incremental methodology implementation
- **Coding:** In progress — Batches 0–3 implemented; Batch 4/5 correctness work underway
- **Repository writes:** Scoped local implementation; no commit or push in this batch
- **Source of truth:** GitHub `main`
- **Primary goal:** Make Apex discover valid Binance USDT perpetual-futures scalp opportunities near current market price while preserving strict risk control, transparent rejection diagnostics, and independent runner qualification.

---

# 1. Product intent

Apex must answer two separate questions for every analyzed symbol:

1. **Is there a valid trade near the current market price?**
2. **If no current entry is executable, what exact future trigger would create a valid trade plan?**

The system must not return only:

> Valid setups exist, but none has a currently executable entry.

When a measurable setup exists but is not executable yet, Apex must preserve and show the complete conditional plan:

- direction;
- setup type;
- trigger condition;
- trigger price or trigger zone;
- preferred future entry zone;
- maximum chase;
- stop-loss;
- TP1;
- TP2;
- optional runner target;
- expected holding horizon;
- invalidation before entry;
- setup expiry;
- exact reason it is not executable now.

This allows the operator to monitor the setup or place an appropriate conditional order without inventing geometry at the time of execution.

Apex must still return **NO_TRADE** when no technically defensible geometry exists.

---

# 2. Core operating principles

## 2.1 Scalp first, runner second

A setup may qualify as a scalp without qualifying as a runner.

A scalp must not be rejected merely because:

- the 1h or 4h trend is opposing;
- broad target space is limited;
- the market is unlikely to trend for hours;
- only TP1 is currently defensible;
- the higher-timeframe structure suggests reversal risk after the scalp objective.

Runner qualification is a second, independent decision made after the scalp opportunity is valid.

### Required result

```text
Scalp: valid long
Runner: not qualified
Higher-timeframe warning: bearish resistance above
Operator instruction: treat as scalp only; reassess for short reversal near the stated zone
```

## 2.2 Pattern detection is not trade approval

The system must preserve the following separation:

```text
market condition
→ pattern or structure detected
→ setup candidate generated
→ entry geometry built
→ quality assessed
→ methodology gate applied
→ current or future execution state assigned
→ portfolio lane retained
```

A visible candle pattern, RSI condition, moving-average crossover, or breakout attempt cannot create a trade by itself.

## 2.3 Technical analysis is probabilistic

Apex should estimate and rank opportunities, not claim certainty.

`READY_NOW` means:

- strategy rules are complete;
- entry geometry is currently valid;
- risk is predefined;
- no hard rejection is active.

It does not mean the trade is guaranteed to win.

## 2.4 No fabricated setup

A future setup may only be displayed when Apex can derive:

- an objective trigger;
- a defensible entry zone;
- structural invalidation;
- at least one net-profitable target;
- a lifecycle and expiry.

If one of these is unavailable, Apex must say why rather than fabricate a plan.

---

# 3. Source methodology

## 3.1 John J. Murphy — market structure authority

Use Murphy-derived principles for:

- trend classification;
- swing structure;
- support and resistance zones;
- role reversal;
- trendlines and channels;
- retracements;
- breakout acceptance;
- failed breakouts;
- structural stops;
- measured and structural targets;
- separate roles for short-, intermediate-, and higher-timeframe trends.

Important implementation interpretation:

- support and resistance are zones, not exact prices;
- a short-term move may occur inside an opposing larger trend;
- higher timeframes define context and constraints, not automatic vetoes;
- targets must come from structure rather than a fixed percentage.

## 3.2 Steve Nison — candle evidence and timing authority

Use Nison-derived principles for:

- completed candle patterns;
- provisional active-candle states;
- reversal warnings;
- continuation evidence;
- candle-pattern context;
- candle plus support/resistance confluence;
- candle plus retracement or moving-average confluence;
- entry timing and failure confirmation.

Important implementation interpretation:

- candlesticks are an evidence layer, not the entire analysis engine;
- a reversal candle may signal exit risk or consolidation, not necessarily an opposite trade;
- candle patterns do not independently provide targets;
- active-candle logic must distinguish provisional shape from completed pattern;
- continuous crypto markets require adaptations for classical gap-based patterns.

## 3.3 Mark Douglas — process and risk authority

Use Douglas-derived principles for:

- uncertainty language;
- predefined risk;
- deterministic execution;
- no chase;
- no emotional override;
- no changing methodology after one loss;
- sample-based evaluation;
- strategy versioning;
- separation of setup quality from trade outcome.

Important implementation interpretation:

- a valid losing trade is not automatically a methodology defect;
- a winning rule violation is still an execution defect;
- edge must be evaluated across a sufficiently large sample;
- risk must be fully defined before approval.

---

# 4. Desired per-symbol opportunity portfolio

Every symbol must be evaluated independently for all lanes below.

## Lane A — CMP scalp

A trade executable now or within a very small volatility-adjusted distance from current price.

Examples:

- micro pullback into support;
- VWAP reclaim or rejection;
- breakout continuation still inside permitted chase;
- liquidity sweep recovery;
- failed micro-breakout reversal;
- momentum continuation after completed trigger;
- range-edge rejection.

## Lane B — confirmation scalp

A scalp whose structure exists but requires one clear completion condition.

Examples:

- candle close above reclaim level;
- close below breakdown level;
- break of trigger candle high or low;
- volume expansion condition;
- micro swing break;
- retest acceptance.

## Lane C — pullback scalp

A valid directional setup where current price is not ideal but a retracement zone is measurable.

The plan must show:

- pullback zone;
- preferred price;
- invalidation;
- trigger required inside the zone;
- maximum chase;
- target hierarchy;
- expiry.

## Lane D — nearby structured entry

A non-immediate but close opportunity based on:

- polarity retest;
- support/resistance test;
- channel boundary;
- trendline reaction;
- retracement confluence;
- range boundary;
- compression edge.

## Lane E — runner opportunity

A larger continuation or reversal with sufficient higher-timeframe authority and target space.

A runner must not be inferred merely because a scalp has multiple targets.

## Lane F — developing future setup

A measurable setup that is incomplete but can be expressed as a conditional plan.

This lane is where:

> Valid setups exist, but none has a currently executable entry

must be converted into useful operator geometry.

## Lane G — no trade

Used only when no lane has a technically defensible present or future setup.

---

# 5. Required output behavior for non-executable setups

## 5.1 Conditional plan contract

Every non-executable but valid setup must contain:

```yaml
symbol:
direction:
lane:
strategy:
state:
current_price:
trigger:
  type:
  level:
  condition:
  confirmation_timeframe:
entry:
  lower:
  preferred:
  upper:
  maximum_chase:
stop:
  price:
  distance_pct:
  structural_basis:
targets:
  - label:
    price:
    reward_risk:
    basis:
holding_horizon:
runner_qualification:
higher_timeframe_warning:
pre_entry_invalidation:
expiry:
reason_not_executable_now:
```

## 5.2 Example operator output

```text
SOLUSDT — CONDITIONAL LONG SCALP

Current price     153.42
Status            Confirmation required
Trigger           3m close above 153.86 with price holding above VWAP
Entry zone        153.86–154.05
Preferred entry   153.92
Maximum chase     154.18
Stop              153.21
TP1               154.74
TP2               155.38
Runner            Not qualified
HTF warning       1h resistance at 155.40–155.75; reassess for reversal there
Expiry            6 x 3m candles
Invalid before    3m close below 153.21 before activation
Why not now       Reclaim has not closed above the trigger level
```

## 5.3 Future-order safety

Apex should not blindly recommend a limit order at the trigger for every strategy.

It must specify the suitable order intent:

- stop-market or stop-limit for confirmed breakout;
- limit order only for a predefined pullback zone;
- alert-only when candle-close confirmation is required;
- no resting order when invalidation or entry geometry can change before trigger.

The output should distinguish:

```text
conditional_order_eligible: true | false
recommended_order_intent: stop | limit | alert_only
```

---

# 6. Timeframe architecture

Timeframes must have strategy-specific roles rather than one universal weighted vote.

## 6.1 CMP and confirmation scalp

| Role | Timeframes |
|---|---|
| Timing | 1m |
| Trigger and refinement | 3m |
| Execution structure | 5m |
| Local context and obstacle map | 15m |
| Risk ceiling and reversal warning | 30m / 1h |
| Macro warning only | 4h |

Higher timeframes may:

- reduce scalp quality;
- shorten targets;
- prohibit runner conversion;
- add an opposite-direction warning.

They should hard-reject a scalp only when they create an immediate structural contradiction, such as entry directly into strong nearby resistance with inadequate reward.

## 6.2 Pullback and nearby structured scalp

| Role | Timeframes |
|---|---|
| Trigger | 3m / 5m |
| Setup structure | 5m / 15m |
| Directional context | 15m / 30m |
| Broader constraint | 1h |
| Macro warning | 4h |

## 6.3 Runner

| Role | Timeframes |
|---|---|
| Entry refinement | 3m / 5m |
| Setup confirmation | 15m |
| Structural authority | 30m / 1h |
| Regime and major obstacle | 4h |

A runner requires substantially stronger higher-timeframe agreement than a scalp.

---

# 7. Scalp methodology

## 7.1 Scalp definition

A scalp is a short-horizon trade whose primary objective is a nearby technically derived move.

It must have:

- liquid market;
- acceptable spread;
- current or conditional entry;
- structural stop;
- net-profitable TP1 after expected fees and slippage;
- clear invalidation;
- limited lifecycle;
- strategy-specific trigger.

It does not require:

- 4h alignment;
- multiple large targets;
- broad trend continuation;
- runner authority;
- universal timeframe agreement.

## 7.2 Minimum scalp quality dimensions

Recommended dimensions:

| Dimension | Purpose |
|---|---|
| Liquidity quality | Can the trade be entered and exited efficiently? |
| Spread and slippage quality | Is the expected move large enough after costs? |
| Local directional edge | Is 1m–5m behavior sufficiently directional? |
| Entry freshness | Is CMP still inside valid geometry? |
| Structural quality | Is the invalidation technically meaningful? |
| Trigger quality | Has the required setup condition completed? |
| TP1 viability | Is the first target defensible and net-profitable? |
| Local contradiction | Is there a nearby obstacle that destroys the trade? |
| Data quality | Are the candles and futures evidence reliable? |

## 7.3 Scalp target requirements

TP1 must be based on the nearest valid objective, such as:

- prior micro swing;
- VWAP or moving-average reversion;
- opposite side of local range;
- breakout expansion objective;
- next 5m/15m structure;
- liquidity pocket;
- measured compression width;
- predefined R objective clipped by structure.

A scalp can be valid with only one meaningful target.

## 7.4 Scalp holding horizon

Holding horizon should derive from:

- trigger timeframe;
- recent ATR;
- distance to target;
- setup type;
- volatility regime.

Example categories:

- ultra-short: 2–10 minutes;
- short scalp: 5–25 minutes;
- extended scalp: 15–60 minutes;
- scalp-to-runner candidate: initially scalp, later promoted.

These are classifications, not fixed guarantees.

---

# 8. Runner methodology

## 8.1 Runner qualification occurs after scalp validity

A runner is permitted only when:

- TP1 has been reached or the setup has clearly activated;
- 15m–1h structure supports continuation;
- remaining target space exists;
- momentum and participation remain healthy;
- no severe exhaustion signal is active;
- price has not reached a major opposing zone;
- the setup has a valid trailing framework.

## 8.2 Runner disqualification

Runner should be denied when:

- 1h/4h structure strongly opposes continuation;
- major support or resistance is near;
- momentum is decelerating;
- volume does not support expansion;
- repeated rejection appears;
- an exhaustion candle or failed breakout emerges;
- the remaining reward is inadequate.

## 8.3 Opposite-direction warning

When runner qualification fails due to higher-timeframe opposition, output:

- the exact opposing zone;
- the signal required for reversal;
- the potential opposite strategy;
- whether the current scalp target lies before that zone;
- an instruction to reassess, not automatically reverse.

---

# 9. Strategy-specific design

Each strategy must define its own:

- eligible regimes;
- timeframe roles;
- trigger;
- confirmation basis;
- entry zone;
- maximum chase;
- stop basis;
- TP1 method;
- runner rules;
- expiry;
- contradiction rules;
- missing-data behavior;
- score profile.

## 9.1 Momentum scalp

### Eligible when

- short-term directional expansion exists;
- relative participation is elevated;
- current price remains within volatility-adjusted chase;
- nearby target space is adequate;
- spread and slippage remain acceptable.

### Reject when

- movement is already exhausted;
- entry is beyond chase;
- TP1 is blocked;
- impulse is unsupported by participation;
- price is moving inside high-noise chop.

### HTF behavior

Opposing HTF reduces runner authority and may reduce scalp score, but does not automatically reject the scalp.

## 9.2 VWAP reclaim or rejection

### Long reclaim

- price trades below or around VWAP;
- completed reclaim occurs;
- short-term structure supports acceptance;
- stop is below failed reclaim structure;
- target is next local resistance.

### Short rejection

Mirror logic.

### Important

VWAP touch alone is not a trigger.

## 9.3 Breakout continuation

Differentiate:

- pre-break setup;
- confirmed break;
- first continuation;
- late chase;
- failed breakout.

The trade must not be rejected only because a runner is unavailable.

## 9.4 Breakout retest

Future plan must be retained whenever:

- breakout level is measurable;
- retest zone can be defined;
- invalidation and target are available.

This is a primary future-order lane.

## 9.5 First pullback continuation

Use:

- completed impulse;
- controlled retracement;
- pullback depth;
- volume contraction;
- support at structure or moving average;
- lower-timeframe confirmation;
- continuation target.

## 9.6 Trend pullback

Must distinguish scalp pullback from runner pullback.

A small pullback inside a 5m trend may be a scalp even when the 1h trend is opposing.

## 9.7 Compression expansion

Use:

- measurable compression;
- declining range or volatility;
- clear boundaries;
- expansion trigger;
- breakout quality;
- measured width target;
- failed expansion handling.

## 9.8 Range reversal

Must require:

- clear range boundaries;
- rejection or sweep;
- acceptable entry near edge;
- target toward midpoint or opposite range area;
- no entry from range midpoint.

## 9.9 Failed breakout reversal

Use:

- break beyond structure;
- failure back inside;
- acceptance inside prior range;
- failed-break extreme as invalidation;
- structural target back through the range.

## 9.10 Liquidity rejection reversal

A wick alone is insufficient.

Require:

- sweep beyond known level;
- close or acceptance back through level;
- local flow or volume support where available;
- defensible stop beyond sweep;
- target to next structure.

## 9.11 Exhaustion reversal

This should generally be:

- an exit warning first;
- a reversal candidate second;
- an approved opposite trade only after completion and risk validation.

---

# 10. Indicator methodology

Indicators must support price structure, not replace it.

## 10.1 RSI

Use RSI for:

- momentum regime;
- divergence candidate;
- failure swing;
- overextension warning;
- relative momentum comparison.

Do not use:

```text
RSI > 70 = automatic short
RSI < 30 = automatic long
```

Thresholds must be strategy- and regime-aware.

## 10.2 MACD

Use MACD for:

- momentum direction;
- acceleration or deceleration;
- histogram contraction;
- trend continuation support;
- divergence candidate.

A crossover alone must not approve a trade.

## 10.3 Moving averages

Use moving averages for:

- trend context;
- dynamic support or resistance;
- pullback location;
- slope;
- extension;
- reclaim or rejection evidence.

Do not require all moving averages to align for every scalp.

## 10.4 VWAP

Use VWAP primarily for intraday execution context:

- reclaim;
- rejection;
- mean reversion;
- acceptance;
- distance and extension.

## 10.5 ATR

ATR must normalize:

- chase limits;
- stop buffer;
- zone width;
- extension;
- target plausibility;
- volatility regime.

Avoid universal fixed-percent geometry where ATR-based geometry is available.

## 10.6 Volume and futures evidence

Where available, use:

- relative volume;
- taker imbalance;
- open-interest change;
- price/OI relationship;
- funding;
- basis;
- order-book depth;
- spread;
- liquidation or forced-flow proxies.

Missing optional evidence should be neutral or explicitly unavailable, not fabricated as zero.

---

# 11. Scoring redesign

## 11.1 Replace one universal profile with lane profiles

Required score profiles:

- `cmp_scalp`;
- `confirmation_scalp`;
- `pullback_scalp`;
- `nearby_structured`;
- `runner`;
- `developing_setup`.

Each lane must have separate:

- weights;
- thresholds;
- hard rejections;
- penalties;
- neutral metrics;
- timeframe interpretation.

## 11.2 Avoid duplicate penalties

The audit must determine whether these represent the same underlying issue:

- conflict penalty;
- higher-timeframe contradiction;
- target-space reduction;
- trend-alignment reduction.

One condition should not be punished four times unless each penalty captures genuinely independent risk.

## 11.3 Hard rejection versus soft penalty

### Hard rejection examples

- insufficient data;
- unacceptable spread;
- no valid stop;
- no net-profitable TP1;
- invalid geometry;
- already invalidated;
- excessive chase;
- entry directly into obstacle with insufficient reward;
- contradictory trigger state.

### Soft penalty examples

- neutral higher timeframe;
- moderate opposing higher timeframe;
- reduced runner space;
- mild extension;
- incomplete optional futures evidence;
- low but acceptable volume confirmation.

## 11.4 No blind threshold loosening

Threshold changes require:

- observed rejection distribution;
- actual versus required values;
- backtest evidence;
- out-of-sample validation;
- separate results by strategy and lane.

---

# 12. Candidate retention and selection

## 12.1 Preserve all generated candidates

Every generated candidate must remain traceable even if rejected.

Required diagnostic fields:

```yaml
candidate_id:
symbol:
strategy:
lane:
direction:
raw_quality:
quality_components:
penalties:
final_score:
required_score:
entry_state:
outcome:
primary_rejection:
secondary_rejections:
actual_vs_required:
counterfactual_lane_validity:
```

## 12.2 Retain one best candidate per lane

Selection must not collapse all strategies into one winner too early.

For every symbol retain:

- best CMP scalp;
- best confirmation scalp;
- best pullback scalp;
- best nearby entry;
- best runner;
- best developing setup;
- best opposite-direction warning.

## 12.3 Collision handling

Resolve only true collisions, such as:

- mutually exclusive long and short entries at the same time;
- duplicate strategies describing the same geometry;
- overlapping entries with the same invalidation and target;
- runner and scalp versions of the exact same trade.

Do not remove different opportunities merely because they share a symbol.

---

# 13. Rejection-trace methodology

## 13.1 Required audit table

For every candidate:

| Field | Description |
|---|---|
| Symbol | Binance futures symbol |
| Strategy | Candidate generator |
| Lane | CMP, confirmation, pullback, nearby, runner, developing |
| Direction | Long or short |
| Entry state | Current conditional state |
| Actual metric | Observed value |
| Required metric | Threshold |
| Rule | Exact rejecting rule |
| Severity | Hard rejection or penalty |
| Justified | Yes, no, or uncertain |
| Counterfactual | Would it pass under correct lane rules? |

## 13.2 Pipeline counters

Every scan should report:

```text
markets discovered
markets screened
symbols shortlisted
symbols fully analyzed
strategies evaluated
candidates generated
candidates with valid geometry
CMP scalp candidates
confirmation scalp candidates
pullback candidates
nearby candidates
runner candidates
developing candidates
rejected by data
rejected by structure
rejected by trigger
rejected by chase
rejected by stop
rejected by TP1 space
rejected by score
rejected by HTF contradiction
rejected by methodology gate
suppressed as duplicate
suppressed by collision
portfolio opportunities retained
currently executable
```

## 13.3 Actual-versus-required diagnostics

Never output only:

> Score too low.

Output:

```text
Final score 56.3; required 58.0.
Largest deductions:
- HTF contradiction: -12.0
- target space: quality 0.41
- provisional trigger: -5.0
Counterfactual:
- passes CMP-scalp floor of 54.0
- fails runner floor of 62.0
```

---

# 14. Methodology gate redesign

## 14.1 Gate purpose

The methodology gate should prevent invalid trades, not erase useful conditional plans.

## 14.2 Gate result types

```text
APPROVED_CURRENT
APPROVED_CONDITIONAL
APPROVED_SCALP_ONLY
APPROVED_RUNNER
DOWNGRADED
REJECTED
DATA_UNAVAILABLE
```

## 14.3 Conditional approval

A setup should receive `APPROVED_CONDITIONAL` when:

- its structure is valid;
- future trigger is objective;
- entry, stop and target geometry are known;
- it is not executable now;
- it has not expired or invalidated.

## 14.4 Scalp-only approval

Use `APPROVED_SCALP_ONLY` when:

- local trade is valid;
- TP1 is viable;
- runner conditions fail;
- HTF opposition is not an immediate local invalidation.

---

# 15. Screening redesign

## 15.1 Preserve hard tradability filters

Continue to reject:

- insufficient volume;
- unacceptable spread;
- stale market;
- incomplete candle history;
- unsupported contracts;
- structurally unusable volatility.

## 15.2 Multi-lane shortlist scoring

The screener should maintain separate shortlist reasons:

- immediate momentum;
- structure proximity;
- compression;
- pullback development;
- reversal development;
- unusual participation;
- range-edge proximity.

A symbol should enter full analysis if it is strong in any valid discovery lane.

## 15.3 Prevent 5m-only blindness

The prefilter may use 5m for efficiency, but it should include lightweight signals from:

- 1m or 3m acceleration;
- 15m structural location;
- unusual spread or volume change;
- compression state;
- proximity to important levels.

## 15.4 Screening audit

Periodically analyze a sample of non-shortlisted symbols to estimate:

- missed valid scalp rate;
- missed runner rate;
- false shortlist rate;
- lane coverage.

---

# 16. Binance data utilization

## 16.1 Minimum required data

- closed OHLCV candles;
- current mark or last price;
- best bid and ask;
- exchange precision;
- contract status;
- 24h liquidity metrics.

## 16.2 Valuable futures evidence

Where reliably available:

- open interest;
- OI change;
- funding;
- premium or basis;
- taker buy/sell activity;
- order-book depth;
- liquidation-related evidence.

## 16.3 Data quality contract

Every evidence field must expose:

```text
available
fresh
source
timestamp
value
fallback_behavior
```

Missing data must not become:

```text
0
false
bearish
bullish
```

unless zero is an actual observed value.

---

# 17. Entry geometry redesign

## 17.1 Volatility-aware chase

Replace universal fallback chase percentages with strategy-specific ATR geometry.

Potential model:

```text
max_chase_distance =
minimum(
    strategy_atr_multiplier × execution_ATR,
    remaining_distance_to_TP1 × chase_fraction,
    risk_geometry_limit
)
```

Exact multipliers must be calibrated.

## 17.2 Structural zones

Every entry must use:

- lower boundary;
- preferred price;
- upper boundary;
- trigger level;
- maximum chase;
- current price relation to zone.

## 17.3 Pre-entry invalidation

A conditional plan can fail before entry.

Examples:

- support breaks before pullback entry;
- reclaim level loses acceptance;
- breakout occurs without volume and immediately fails;
- target space collapses;
- setup expires.

This must cancel the future plan.

---

# 18. Stop-loss methodology

Stop hierarchy:

1. strategy invalidation;
2. structural swing;
3. support/resistance zone boundary;
4. ATR or tick buffer;
5. spread and slippage allowance;
6. liquidation and account-risk check where account data is used.

Prohibited:

- arbitrary stop chosen to manufacture R:R;
- same fixed percentage for every symbol;
- stop inside entry zone;
- widening after activation without a predefined rule;
- stop beyond liquidation;
- no-stop approval.

---

# 19. Target and management methodology

## 19.1 Target hierarchy

1. nearest structural objective;
2. setup-specific measured objective;
3. next timeframe obstacle;
4. optional extension;
5. runner target.

## 19.2 Scalp management

A scalp plan should define:

- TP1;
- full-exit or partial behavior;
- time stop;
- momentum-failure exit;
- breakeven behavior only when appropriate;
- no automatic runner assumption.

## 19.3 Runner promotion

A scalp becomes a runner only when a promotion condition is met.

Example:

```text
TP1 reached
and 5m structure remains intact
and 15m acceptance continues
and no HTF reversal trigger is active
and remaining target space is adequate
```

## 19.4 Opposite reversal watch

When the scalp approaches a major opposing zone, Apex should output:

- zone;
- reversal trigger;
- invalidation;
- candidate opposite strategy;
- instruction to wait for confirmation.

---

# 20. Implementation batches

## Batch 0 — Freeze methodology baseline

### Goal

Capture current behavior before changing logic.

### Work

- record current `main` commit;
- record resolved config fingerprint;
- save representative scan JSON;
- save representative analyze JSON;
- identify one known bad trade;
- identify symbols with conditional setups;
- record current rejection counts.

### Deliverables

- baseline report;
- baseline candidate funnel;
- current configuration inventory;
- reproducible symbol set.

### Exit criteria

No methodology change begins until the baseline can be reproduced.

---

## Batch 1 — Complete rejection observability

### Goal

Find exactly where candidates disappear.

### Work

- add candidate lineage;
- record generator strategy;
- record lane;
- record raw score;
- record penalties;
- record actual versus required thresholds;
- record primary and secondary rejection reasons;
- add stage counters;
- preserve rejected candidate diagnostics in JSON.

### Tests

- every generated candidate has one terminal outcome;
- counts balance across pipeline;
- no candidate disappears silently;
- rejection message includes actual and required values;
- scan and analyze produce identical diagnostics for the same symbol and timestamp.

### Exit criteria

For any no-trade symbol, Apex can explain every candidate and its exact rejection.

---

## Batch 2 — Conditional future-plan preservation

### Goal

Convert valid but non-executable candidates into complete future plans.

### Work

- introduce conditional approval;
- retain trigger geometry;
- retain future entry zone;
- build stop and targets from trigger-relative geometry;
- add pre-entry invalidation;
- add expiry;
- add order-intent classification;
- expose conditional plans in portfolio and CLI.

### Tests

- valid retest candidate shows trigger, entry, stop and targets;
- invalid geometry remains no-trade;
- future plan cancels when pre-entry invalidation occurs;
- no future plan uses current-price geometry when trigger-relative geometry is required;
- future plan is stable between scan and analyze.

### Exit criteria

“Valid setups exist but none executable” always produces a useful conditional plan when defensible geometry exists.

---

## Batch 3 — Opportunity-lane portfolio

### Goal

Stop global single-winner collapse.

### Work

- assign lane to every candidate;
- retain best candidate per lane;
- preserve long and short future plans where non-conflicting;
- deduplicate only equivalent geometry;
- add opposite-direction warning lane;
- keep compatibility selected setup temporarily.

### Tests

- one symbol can retain CMP scalp and runner separately;
- one symbol can retain long scalp and short reversal watch;
- duplicate strategies collapse correctly;
- different entry prices remain separate opportunities;
- portfolio order is deterministic.

### Exit criteria

Every symbol exposes the full set of materially different opportunities.

---

## Batch 4 — Scalp and runner score separation

### Goal

Create horizon-aware methodology profiles.

### Work

- define scalp quality components;
- define runner quality components;
- define lane-specific thresholds;
- classify hard rejections separately from soft penalties;
- prevent duplicate penalties;
- add lane-specific HTF contradiction behavior;
- add TP1-specific scalp target quality.

### Tests

- valid scalp can pass while runner fails;
- HTF opposition reduces or blocks runner without automatically blocking scalp;
- trade with no net TP1 is rejected;
- severe immediate HTF obstacle rejects scalp;
- moderate distant HTF opposition creates warning only.

### Exit criteria

Scalp and runner approval are independent and explainable.

---

## Batch 5 — Timeframe-role routing

### Goal

Replace universal timeframe voting with strategy-specific roles.

### Work

- define role maps per lane;
- make 1m/3m/5m authoritative for scalp execution;
- make 15m contextual for scalp;
- make 30m/1h/4h constraints and runner authority;
- distinguish local contradiction from distant macro opposition;
- add horizon-aware conflict reporting.

### Tests

- local aligned scalp survives distant HTF opposition;
- immediate HTF obstacle rejects poor reward geometry;
- runner requires 15m–1h support;
- timeframe conflicts are reported rather than averaged into an opaque score.

### Exit criteria

Timeframe influence matches the intended holding horizon.

---

## Batch 6 — Strategy methodology corrections

### Goal

Audit and correct every enabled strategy.

### Work

For each strategy document:

- regime;
- timeframe roles;
- trigger;
- confirmation;
- provisional behavior;
- entry geometry;
- chase;
- stop;
- targets;
- expiry;
- scalp rules;
- runner rules;
- reversal warning;
- data requirements;
- rejection rules.

Implement one coherent strategy family at a time.

Suggested order:

1. momentum scalp;
2. VWAP reclaim/rejection;
3. breakout continuation;
4. breakout retest;
5. first pullback continuation;
6. trend pullback;
7. compression expansion;
8. range reversal;
9. failed breakout reversal;
10. liquidity rejection reversal;
11. exhaustion reversal.

### Exit criteria

No strategy relies on generic undocumented behavior.

---

## Batch 7 — Indicator and feature calibration

### Goal

Make indicators regime-aware and remove duplicated evidence.

### Work

- inventory all indicator periods and thresholds;
- identify correlated evidence;
- verify normalization by symbol volatility;
- separate evidence from trigger;
- remove automatic overbought/oversold reversal assumptions;
- calibrate ATR, volume, momentum and extension features;
- version configuration.

### Exit criteria

Every threshold has a purpose, lane and validation plan.

---

## Batch 8 — Binance futures evidence integration

### Goal

Improve short-horizon analysis using available market evidence.

### Work

- audit existing futures evidence;
- add availability and freshness metadata;
- integrate OI and OI change where reliable;
- integrate taker-flow evidence where reliable;
- evaluate order-book and depth evidence;
- add funding and basis as context;
- maintain fail-soft behavior.

### Exit criteria

Optional evidence improves ranking without fabricating missing values or blocking analysis unnecessarily.

---

## Batch 9 — Screening lane expansion

### Goal

Reduce missed opportunities before full analysis.

### Work

- add multi-lane shortlist features;
- include micro acceleration;
- include 15m structure proximity;
- include compression and range-edge lanes;
- audit non-shortlisted sample;
- preserve hard liquidity and tradability gates.

### Exit criteria

Screening recall improves without sending the entire unusable universe into expensive analysis.

---

## Batch 10 — Scalp lifecycle and runner promotion

### Goal

Manage initial scalp and optional runner correctly.

### Work

- define scalp TP1 lifecycle;
- define time exits;
- define momentum failure;
- define runner promotion;
- define HTF reversal warning;
- define opposite setup reassessment;
- prevent 1m noise from prematurely managing an approved runner.

### Exit criteria

Apex can state:

```text
Scalp valid
Runner pending
Runner promoted
Runner denied
Opposite reversal watch
```

---

## Batch 11 — Backtesting and replay correctness

### Goal

Validate methodology chronologically.

### Work

- replay every lane without look-ahead;
- model conditional activation;
- model unfilled future plans;
- model pre-entry invalidation;
- model fees, slippage and spread;
- model TP1 and runner separately;
- record MFE and MAE;
- evaluate rejected-candidate counterfactuals;
- segment results by strategy, lane, volatility and timeframe conflict.

### Required metrics

- opportunities generated;
- fill rate;
- expiry rate;
- pre-entry invalidation rate;
- win rate;
- expectancy;
- profit factor;
- average win and loss;
- MFE;
- MAE;
- drawdown;
- time in trade;
- scalp-only performance;
- runner conversion rate;
- runner incremental expectancy;
- false rejection rate;
- false approval rate.

### Exit criteria

No threshold is promoted based only on anecdotal live trades.

---

## Batch 12 — Calibration and promotion gates

### Goal

Promote only stable methodology.

### Work

- train/validation/test time splits;
- walk-forward evaluation;
- symbol segmentation;
- regime segmentation;
- parameter sensitivity;
- minimum sample requirements;
- stability checks;
- strategy version fingerprints.

### Promotion gates

A strategy/lane should require:

- positive out-of-sample expectancy;
- acceptable drawdown;
- stable performance across multiple periods;
- sufficient sample size;
- no dependence on one symbol;
- tolerable fee/slippage sensitivity;
- controlled parameter sensitivity.

---

## Batch 13 — Paper validation

### Goal

Observe realistic live behavior without financial risk.

### Work

- record scan and analyze outputs;
- record conditional plans;
- reconcile triggers and fills;
- track latency;
- track spread and slippage;
- track invalidations;
- compare predicted versus realized horizons;
- inspect no-trade and rejected candidates.

### Exit criteria

Paper behavior matches backtest semantics and no hidden candidate suppression remains.

---

## Batch 14 — Final documentation and operator workflow

### Goal

Make methodology understandable and auditable.

### Documentation

- strategy catalogue;
- timeframe roles;
- lane definitions;
- score profiles;
- threshold provenance;
- rejection glossary;
- conditional-order guidance;
- scalp-to-runner lifecycle;
- risk limitations;
- validation results;
- configuration examples.

### Operator workflow

```text
1. Run scan.
2. Review executable CMP scalps.
3. Review conditional future plans.
4. Inspect runner authority separately.
5. Check HTF reversal warning.
6. Use analyze for deep evidence.
7. Do not execute expired or invalidated plans.
8. Record outcome as process-valid or process-invalid independently from profit.
```

---

# 21. Safety and quality rules for implementation

For every code batch:

1. inspect fresh GitHub `main`;
2. keep changes focused;
3. do not modify CLI design unless required to expose methodology;
4. preserve shared scan/analyze authority;
5. maintain deterministic behavior;
6. use config-driven thresholds;
7. add focused tests;
8. do not commit or push without explicit approval;
9. never claim validation passed without terminal output;
10. report:
   - patch completion;
   - current batch completion;
   - overall plan completion.

---

# 22. Definition of success

Apex is successful when it can do all of the following:

- discover current scalps near CMP;
- show complete conditional future plans;
- retain separate opportunities per symbol;
- distinguish scalp from runner;
- warn about higher-timeframe reversal zones;
- avoid forcing trades;
- explain every rejection with actual versus required values;
- use Binance data without fabricating missing evidence;
- generate structural entry, stop and target geometry;
- validate methodology through chronological research;
- preserve uncertainty and predefined risk.

The objective is not to maximize the number of signals.

The objective is to stop losing valid opportunities through incorrect methodology while continuing to reject structurally poor trades.
