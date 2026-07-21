# Apex Trading Project — Complete Trade Discovery and Methodology Correction Plan

## Status

- **Phase:** Methodology and implementation planning
- **Coding:** Not started
- **Repository writes:** None
- **Source of truth:** GitHub `main`
- **Target document:** `docs/fixes.md`
- **Primary objective:** Make Apex retain and correctly rank technically valid Binance USDT perpetual-futures opportunities near CMP without forcing trades, bypassing required evidence, fabricating geometry, or allowing weak reward structures.
- **Architecture constraint:** Preserve the shared canonical analysis authority used by both `apex scan` and `apex analyze SYMBOL`. The only difference between those commands must remain symbol selection and presentation context.
- **Validation constraint:** No batch is complete until its focused tests and required repository validation have been run and actual output has been reviewed.

---

# 1. Executive summary

The latest candidate-specific methodology and portfolio changes are directionally correct and must not be reverted wholesale.

The following improvements must be preserved:

1. Candidate-specific methodology routing.
2. Separate opportunity lanes for CMP scalp, confirmation scalp, pullback scalp, nearby structured setup, runner, and developing setup.
3. Separation between a setup existing near CMP and actual execution permission.
4. Portfolio distinctions between actionable CMP, confirmation CMP, nearby, follow-up, runner, and no valid setup.
5. Rich execution geometry in CLI output:
   - CMP;
   - ideal entry;
   - entry range;
   - maximum chase;
   - stop;
   - TP1–TP3;
   - trade quality;
   - execution quality;
   - main risk.

The current system still has two opposite failure modes:

- **valid candidates are suppressed** because one broad market-state label or higher-timeframe disagreement is treated as a universal veto;
- **weak candidates can survive** because lane exceptions, geometry checks, evidence checks, execution scoring, and ranking are applied in the wrong order or with conflated semantics.

The correction must therefore not simply “loosen filters.” It must make the pipeline more precise.

The required end-state is:

```text
local candidate generation
→ mandatory evidence validation
→ structural geometry validation
→ execution-timeframe state
→ setup-timeframe state
→ higher-timeframe relationship
→ lane and holding-horizon assignment
→ execution-state classification
→ scalp approval
→ independent runner qualification
→ portfolio selection
→ transparent ranking
→ truthful CLI/JSON presentation
```

---

# 2. Non-negotiable product principles

## 2.1 Do not force trades

Apex may return zero executable opportunities.

The goal is not to increase signal count mechanically. The goal is to stop valid trades from being incorrectly erased while rejecting weak trades for explicit, technically defensible reasons.

## 2.2 Pattern detection is not trade approval

A detected breakout, retest, reversal candle, RSI condition, VWAP interaction, or momentum burst creates evidence or a candidate. It does not automatically create a trade.

Every displayed trade must survive:

- data validity;
- tradability;
- strategy-specific mandatory evidence;
- defensible entry;
- structural invalidation;
- credible target;
- net reward after costs;
- chase control;
- execution-state rules;
- methodology rules;
- collision and duplicate handling.

## 2.3 Analysis and execution remain separate

A bullish or bearish market bias does not equal an executable trade.

A valid setup can be:

- ready now;
- aggressive now;
- confirmation required;
- pullback preferred;
- retest preferred;
- reclaim required;
- approaching;
- developing;
- late;
- missed;
- invalidated;
- no trade.

## 2.4 Scalp validity and runner validity are separate

A scalp can be valid even when higher-timeframe continuation is not.

Runner qualification must be a later, independent decision.

## 2.5 Higher timeframes constrain; they do not automatically veto

For short-horizon trades:

- 1m/3m provide trigger and microstructure;
- 5m provides execution structure and invalidation;
- 15m provides immediate context;
- 30m provides dominant session structure;
- 1h/4h provide major obstacles, broad bias, and runner authority.

A 30m or 1h disagreement may:

- reduce target distance;
- require stronger confirmation;
- reduce alignment score;
- shorten expected holding duration;
- disable runner treatment;
- add an exit condition.

It must not automatically erase a valid local scalp unless it creates direct structural opposition that destroys reward geometry.

## 2.6 Candlesticks are evidence, not target generators

Candle patterns can strengthen timing, confirmation, reversal warnings, and failure logic.

They must not independently generate arbitrary targets or bypass trend, structure, liquidity, stop, or reward checks.

## 2.7 Risk and uncertainty must be explicit

`READY_NOW` means execution rules are complete and risk geometry is valid. It does not mean the trade is certain to win.

Every approved opportunity must have:

- a predefined invalidation;
- a valid stop;
- at least one credible target;
- a known expiry or lifecycle;
- an explicit uncertainty statement in explanatory output.

---

# 3. Confirmed defects to correct

## 3.1 Eligibility ordering is unsafe

Current behavior can:

- reject a scalp at a prohibited-state check before evaluating whether the apparent conflict is only higher-timeframe directional disagreement;
- allow a scalp exception before rejecting missing mandatory evidence.

This creates both over-suppression and under-validation.

### Required eligibility order

1. Data validity.
2. Market tradability.
3. Candidate-specific mandatory evidence.
4. Entry, stop, target, and cost geometry.
5. Execution-timeframe compatibility.
6. Setup-timeframe compatibility.
7. Higher-timeframe directional relationship.
8. Lane and holding horizon.
9. Execution-state permission.
10. Runner qualification.
11. Portfolio selection.

No lane exception may bypass steps 1–4.

## 3.2 One canonical market state is too narrow

A single `PrimaryMarketState` cannot represent:

- 5m pullback inside a 30m uptrend;
- 3m short exhaustion reversal while 15m remains bullish;
- 5m breakdown attempt inside a 1h range;
- 1m momentum scalp during 15m compression;
- local failed breakout while 30m remains trending.

The system must represent separate analytical layers.

## 3.3 HTF conflict is not direction-aware or severity-aware enough

A 5m short against a confirmed 30m long continuation is not equivalent to:

- mild bullish drift;
- neutral 30m context;
- direct nearby 30m support;
- confirmed 30m breakout and reclaim;
- truly chaotic 5m execution structure.

The engine needs explicit relationship and severity classifications.

## 3.4 Lane inference is too dependent on CMP proximity or entry mode

Holding horizon cannot be inferred mainly from whether price is near CMP or whether an entry uses retest/reclaim logic.

Lane must derive from:

- setup timeframe;
- invalidation timeframe;
- target timeframe;
- ATR-normalized target distance;
- expected bars to target;
- lifecycle model;
- runner authority;
- entry geometry.

## 3.5 Weak reward geometry survives

Examples such as:

- 0.21R;
- 0.18R;
- 0.66R;
- 0.71R;

must not survive as valid displayed trades unless a separately calibrated strategy explicitly supports that payoff after costs. No such proven exception currently exists.

## 3.6 Nearby entries can equal CMP

When:

```text
CMP == ideal entry
CMP is inside the entry zone
```

the candidate cannot truthfully remain a nearby setup.

It must be classified as:

- current market entry;
- current confirmation setup;
- or invalid/suspicious geometry.

## 3.7 Generator geometry is being overwritten or collapsed

Breakout-retest and other structured strategies must preserve:

- original breakout level;
- retest-zone low/high;
- acceptable penetration;
- preferred retest price;
- confirmation requirement;
- trigger-relative stop and targets.

Current price must not overwrite strategy-generated geometry.

## 3.8 Execution quality can be falsely perfect

A candidate with incomplete confirmation cannot have `100/100` execution quality.

Execution quality must include more than CMP proximity.

## 3.9 Confidence, setup quality, and execution quality are conflated

One score cannot truthfully represent:

- pattern validity;
- direction alignment;
- structural quality;
- execution maturity;
- reward quality;
- timing;
- data quality.

## 3.10 CLI ordering looks like ranking but may not be ranking

`#1`, `#2`, etc. visually imply recommendation order.

The order must either become a true global ranking or be relabeled as non-ranked opportunity order.

## 3.11 CLI methodology context was removed

A direction-only header such as:

```text
BTCUSDT — SHORT
```

is insufficient.

The operator must see:

- strategy;
- relationship to HTF;
- actionability;
- state;
- lane or sequence role.

## 3.12 Late continuation and reversal risk are not sufficiently protected

A coin that has already travelled heavily downward must not be shorted merely because momentum is bearish.

The engine must distinguish:

- fresh breakdown;
- first continuation;
- mature continuation;
- late chase;
- exhaustion;
- failed breakdown;
- reversal watch.

## 3.13 Target generation is incomplete or weak

The renderer already supports multiple targets. Missing TP2/TP3 is primarily a generation and qualification issue.

Only one target is acceptable when only one defensible target exists. The setup must be rejected when that sole target produces unacceptable reward.

## 3.14 Internal candidate identifiers leak into operator output

IDs such as:

```text
breakout_retest:short:0
```

are useful for diagnostics and JSON, but should not be primary operator labels.

## 3.15 Price formatting is not optimized for readability

Terminal display should be adaptive and tick-size aware while preserving full precision internally and in JSON.

---

# 4. Target architecture

## 4.1 Multi-layer market-state model

Every candidate must receive separate state layers.

### A. Execution state

What the trigger timeframes are doing now.

Examples:

- directional expansion;
- micro pullback;
- micro reclaim;
- rejection;
- failed micro-breakout;
- compression;
- local chop;
- local chaos;
- exhaustion.

### B. Setup state

What pattern exists on the setup timeframe.

Examples:

- breakout attempt;
- confirmed breakout;
- breakout retest;
- first pullback;
- trend pullback;
- range-edge rejection;
- failed breakout;
- reversal attempt;
- structural reversal confirmed.

### C. Context state

What 15m/30m structure is doing.

Examples:

- trending up;
- trending down;
- range;
- compression;
- transition;
- post-breakout;
- post-breakdown.

### D. Structural bias

What 30m/1h authority implies.

Examples:

- bullish;
- bearish;
- neutral;
- mixed;
- strong bullish continuation;
- strong bearish continuation;
- major obstacle nearby.

### E. Risk condition

Independent execution and market-quality conditions.

Examples:

- liquid;
- illiquid;
- normal spread;
- abnormal spread;
- stale;
- extended;
- high volatility;
- low target space;
- data incomplete;
- execution chaos.

## 4.2 Timeframe relationship model

Every candidate must be classified as one of:

- `WITH_TREND`
- `MIXED_ALIGNMENT`
- `COUNTERTREND_SCALP`
- `REVERSAL_ATTEMPT`
- `STRUCTURAL_REVERSAL_CONFIRMED`

The classification must include severity:

- none;
- mild;
- moderate;
- strong;
- direct structural opposition.

## 4.3 Consequence model

| Relationship | Expected treatment |
|---|---|
| With trend | Normal targets, normal quality, runner may qualify |
| Mild conflict | Small alignment penalty |
| Mixed alignment | Reduced quality or confirmation requirement |
| Strong conflict | Smaller TP, shorter horizon, no runner |
| Direct structural opposition | Confirmation required or reject if reward is destroyed |
| Confirmed opposite breakout | Scalp-only with exceptional evidence, otherwise reject |
| True execution chaos | Hard reject |

## 4.4 Candidate lifecycle

```text
generated
→ evidence_valid
→ geometry_valid
→ locally_compatible
→ HTF_classified
→ lane_assigned
→ execution_state_assigned
→ approved_current / approved_conditional / scalp_only / runner / rejected
→ portfolio_retained
→ ranked
→ rendered
```

Every transition must leave diagnostics.

---

# 5. Score model

## 5.1 Required independent dimensions

Each candidate must expose:

| Dimension | Meaning |
|---|---|
| Pattern confidence | Strength of the detected setup/pattern |
| Directional alignment | Agreement across execution, setup, context, and HTF |
| Setup quality | Structure, invalidation, and target credibility |
| Execution quality | Location, chase, trigger maturity, spread, and freshness |
| Reward quality | R:R, target credibility, and cost-adjusted reward |
| Timing quality | Early, current, late, missed, or invalidated |
| Data confidence | Completeness, freshness, and evidence availability |
| Overall trade quality | Weighted summary only |

## 5.2 Overall score is not a hard-rule replacement

A candidate must not pass merely because a weighted score is high.

Explicit blocking rules remain authoritative:

- missing mandatory evidence;
- wrong-side stop;
- wrong-side target;
- inadequate TP1;
- excessive chase;
- stale data;
- invalid trigger;
- no structural invalidation;
- unacceptable spread;
- direct obstacle destroying reward.

## 5.3 Lane-specific scoring profiles

Required profiles:

- `cmp_scalp`;
- `confirmation_scalp`;
- `pullback_scalp`;
- `nearby_structured`;
- `runner`;
- `developing_setup`.

Each profile must have separate:

- weights;
- score floor;
- hard gates;
- soft penalties;
- HTF consequences;
- target requirements;
- execution requirements.

## 5.4 Avoid duplicate penalties

The implementation must audit whether these metrics punish the same fact multiple times:

- trend conflict;
- HTF contradiction;
- directional alignment;
- target-space reduction;
- runner denial;
- setup quality penalty.

One underlying conflict must not be counted repeatedly unless each consequence reflects a distinct risk.

---

# 6. Geometry rules

## 6.1 Required structural checks

Before portfolio selection, every candidate must pass:

- entry zone is valid;
- preferred entry lies within zone;
- stop is on the correct side;
- targets are on the correct side;
- target ordering is correct;
- stop is outside entry zone;
- chase boundary is directionally correct;
- TP1 R:R meets lane threshold;
- expected costs do not eliminate reward;
- stop distance is plausible for the lane;
- target quality meets hard floor;
- geometry uses the same entry reference.

## 6.2 Initial configurable reward floors

Initial conservative defaults for implementation and testing:

| Lane | Minimum TP1 reward |
|---|---:|
| CMP scalp | 1.00R |
| Confirmation scalp | 1.00R |
| Pullback scalp | 1.20R |
| Nearby structured | 1.25R |
| Runner | broader target at least 1.80R |

These values must be configuration-driven and later calibrated. They are not permanent universal truths.

## 6.3 Required geometry diagnostics

Every rejected candidate must show:

- actual TP1 R:R;
- required TP1 R:R;
- stop distance percent;
- target distance percent;
- expected cost percent;
- target quality;
- selected entry reference;
- rejecting rule;
- lane threshold.

## 6.4 Entry reference authority

All stop, target, R:R, and chase calculations must use the same canonical selected entry:

- market entry when truly immediate;
- preferred zone entry for conditional planning;
- trigger-relative entry where required by strategy.

CMP may be used only when CMP is genuinely the selected entry.

---

# 7. Execution-quality redesign

## 7.1 Suggested components

- 25% entry location;
- 20% trigger completeness;
- 15% chase and freshness;
- 15% spread and slippage;
- 15% stop feasibility;
- 10% active-candle and data quality.

Exact weights must remain configurable.

## 7.2 Hard caps

Initial explicit caps:

| Condition | Maximum execution quality |
|---|---:|
| Required confirmation incomplete | 69 |
| Active candle provisional | 74 |
| Outside valid entry zone | 49 |
| Beyond maximum chase | 0 and reject |
| Stale market data | 0 and reject |
| Invalid stop geometry | 0 and reject |

CMP equaling ideal entry may improve location quality but cannot override trigger or data deficiencies.

---

# 8. Extension, continuation, and reversal protection

## 8.1 Required measurements

Before approving continuation:

- impulse distance in ATR;
- distance from pre-break consolidation;
- remaining distance to next structural target;
- percentage of measured objective already consumed;
- VWAP/EMA extension;
- recent swing progress;
- lower/upper wick recovery;
- momentum acceleration or deceleration;
- volume continuation or exhaustion;
- OI/price relationship where available;
- failed new-low/new-high attempts;
- reclaim or failure structure.

## 8.2 New continuation states

- `FRESH_CONTINUATION`
- `MATURE_CONTINUATION`
- `LATE_CHASE`
- `EXHAUSTION_WARNING`
- `FAILED_BREAKDOWN`
- `FAILED_BREAKOUT`
- `REVERSAL_WATCH`

## 8.3 Allowed outcomes

An extended bearish move may become:

- no new short;
- short scalp only with limited target;
- long reclaim watch.

It must not become an automatic long until the reclaim or structural reversal trigger completes.

## 8.4 Candle interpretation

A reversal candle after a large decline can mean:

- short exit warning;
- consolidation risk;
- long reversal candidate;
- confirmed long only after structure and confirmation.

The same principle applies inversely after a large advance.

---

# 9. Target-generation redesign

## 9.1 Target hierarchy

1. Nearest local structural objective.
2. Strategy-specific measured objective.
3. Next timeframe obstacle.
4. Optional extension target.
5. Runner target.

## 9.2 Rules

- TP1 is mandatory.
- TP2 exists only when a second defensible structure exists.
- TP3 exists only when a third defensible objective exists.
- Targets must be distinct after exchange tick rounding.
- TP2 must be farther than TP1.
- TP3 must be farther than TP2.
- Partial percentages must remain coherent.
- Runner targets require runner qualification.
- One strong target is better than three fabricated targets.
- A setup with only one weak target must be rejected.

## 9.3 Target quality

Target quality must include:

- structural strength;
- target room;
- obstacle density;
- probability of reaching target before invalidation;
- cost-adjusted reward;
- timeframe relevance;
- whether the target is already partially consumed.

---

# 10. Ranking redesign

## 10.1 Ranking eligibility

Only hard-valid candidates may enter recommendation ranking.

Rejected or invalid candidates remain in diagnostics, not ranked opportunity cards.

## 10.2 Ranking precedence

1. No hard geometry or evidence defect.
2. Execution state.
3. TP1 R:R.
4. Target quality.
5. Setup quality.
6. Execution quality.
7. HTF relationship.
8. Extension/chase burden.
9. Data quality.
10. Stable deterministic tie-breaker.

## 10.3 Ranking score

A separate `rank_score` may be calculated, but it must not replace the component fields or hard rules.

## 10.4 CLI numbering

When true ranking is implemented, use:

```text
Rank #1
Rank #2
```

Until then, use:

```text
Opportunity 1
Opportunity 2
```

and state that order is not a recommendation.

---

# 11. CLI and JSON truthfulness

## 11.1 Compact card header

Recommended:

```text
#1 CLO/USDT — SHORT
Momentum Breakout · Late continuation · Confirmation required
Countertrend scalp · Runner disabled
```

## 11.2 Required card fields

- strategy;
- direction;
- lane;
- execution state;
- actionability;
- timeframe relationship;
- continuation/extension state;
- CMP;
- ideal entry;
- entry range;
- trigger;
- maximum chase;
- stop;
- TP1–TP3;
- TP1 R:R;
- setup quality;
- execution quality;
- target quality;
- HTF alignment;
- overall trade quality;
- main risk;
- expiry.

## 11.3 Raw IDs

Raw `candidate_id` remains in:

- JSON;
- explain mode;
- diagnostic reports.

Normal text should use human-readable strategy names.

## 11.4 Adaptive price formatting

Recommended display behavior:

| Price | Example display |
|---:|---:|
| `153.428191` | `153.43` |
| `4.89321` | `4.89` |
| `0.928191` | `0.9282` |
| `0.0948103` | `0.09481` |
| `0.00480923` | `0.004809` |
| `0.000047819` | `0.00004782` |

Best rule:

```text
display decimals = min(exchange precision, adaptive readability precision)
```

Internal calculations and JSON preserve original precision.

## 11.5 Explain mode

Explain mode must show:

- why candidate passed or failed;
- actual versus required thresholds;
- all score components;
- HTF relationship and consequence;
- lane decision;
- runner decision;
- geometry source;
- extension state;
- target basis;
- rejection stage;
- collision/duplicate result.

---

# 12. Diagnostics and audit contracts

## 12.1 Candidate rejection trace

Required fields:

```yaml
candidate_id:
symbol:
strategy:
direction:
lane:
execution_timeframe:
setup_timeframe:
context_timeframe:
holding_horizon:
execution_state:
setup_state:
context_state:
structural_bias:
risk_condition:
timeframe_relationship:
relationship_severity:
mandatory_evidence:
missing_evidence:
entry_geometry:
stop_geometry:
target_geometry:
quality_components:
penalties:
hard_rejections:
final_score:
required_score:
outcome:
primary_rejection:
secondary_rejections:
actual_vs_required:
runner_qualified:
counterfactual_lane_validity:
```

## 12.2 Pipeline counters

Every scan diagnostic should report:

```text
markets discovered
markets screened
symbols shortlisted
symbols analyzed
strategies evaluated
candidates generated
candidates with mandatory evidence
candidates with valid geometry
CMP scalp candidates
confirmation scalp candidates
pullback scalp candidates
nearby candidates
runner candidates
developing candidates
rejected by data
rejected by tradability
rejected by mandatory evidence
rejected by invalid geometry
rejected by stop
rejected by target
rejected by TP1 R:R
rejected by costs
rejected by trigger
rejected by chase
rejected by execution chaos
rejected by direct HTF opposition
downgraded by HTF conflict
runner denied
suppressed as duplicate
suppressed by collision
portfolio opportunities retained
currently executable
```

## 12.3 Stage attribution

Every rejection must identify the exact stage:

- generator;
- evidence validation;
- geometry builder;
- methodology gate;
- actionability;
- portfolio selection;
- collision handling;
- serialization;
- rendering.

---

# 13. Implementation strategy — safe long batches

The work should be implemented in the following ordered batches. Each batch must be coherent, independently testable, and leave the repository in a valid state.

---

# Batch 0 — Baseline capture and source mapping

## Goal

Capture reproducible evidence for known bad examples and map the exact source path before changing behavior.

## Tasks

1. Save JSON for:
   - `CLOUSDT`;
   - `ERAUSDT`;
   - `VANRYUSDT`;
   - one current full scan.
2. Add `HEIUSDT` if reproducible.
3. Identify each candidate’s path through:
   - strategy generator;
   - entry normalization;
   - candidate-to-setup conversion;
   - evidence validation;
   - methodology eligibility;
   - actionability;
   - portfolio selection;
   - serialization;
   - CLI renderer.
4. Record:
   - candidate ID;
   - raw entry;
   - normalized entry;
   - selected entry;
   - stop;
   - targets;
   - TP1 R:R;
   - target quality;
   - execution quality;
   - methodology result;
   - portfolio lane.
5. Confirm whether the known defects originate in one stage or multiple stages.
6. Create or update a focused geometry audit report under `data/reports/geometry_audit/`.

## Required commands

```bash
cd ~/data_drive/apex
source .venv/bin/activate

mkdir -p data/reports/geometry_audit

apex analyze CLOUSDT --output json \
  > data/reports/geometry_audit/clo.json

apex analyze ERAUSDT --output json \
  > data/reports/geometry_audit/era.json

apex analyze VANRYUSDT --output json \
  > data/reports/geometry_audit/vanry.json

apex scan --output json \
  > data/reports/geometry_audit/scan.json

git status --short
```

## Deliverables

- defect origin matrix;
- impacted files list;
- current test coverage map;
- no production behavior change.

## Acceptance criteria

- Every known bad candidate can be traced from generation to display.
- No assumption remains about whether the problem is generator, normalization, gate, portfolio, serialization, or rendering.
- Baseline JSON is retained for before/after comparison.

---

# Batch 1 — Domain contracts for layered state and score dimensions

## Goal

Introduce the contracts needed to represent reality without changing eligibility behavior yet.

## Tasks

1. Add or extend domain enums/models for:
   - execution state;
   - setup state;
   - context state;
   - structural bias;
   - risk condition;
   - timeframe relationship;
   - relationship severity;
   - continuation/extension state.
2. Add score component fields:
   - pattern confidence;
   - directional alignment;
   - setup quality;
   - execution quality;
   - reward quality;
   - timing quality;
   - data confidence;
   - overall trade quality;
   - rank score.
3. Preserve legacy compatibility fields temporarily.
4. Define canonical human-readable labels.
5. Define JSON serialization.
6. Ensure defaults do not fabricate certainty.
7. Update fixtures/builders used by tests.

## Tests

- enum serialization round trips;
- deterministic labels;
- backward-compatible loading where required;
- no accidental mapping of confidence and quality to the same field;
- absent optional values remain unavailable, not zero.

## Acceptance criteria

- New fields exist and serialize.
- Existing analysis behavior remains unchanged.
- Legacy consumers do not break.
- No score is silently copied into another semantic field.

---

# Batch 2 — Eligibility pipeline ordering and mandatory-evidence safety

## Goal

Fix the highest-risk correctness defect.

## Tasks

1. Refactor eligibility into explicit ordered stages.
2. Ensure data/tradability checks run first.
3. Ensure mandatory evidence runs before all lane exceptions.
4. Ensure geometry safety runs before market-state exceptions.
5. Separate execution chaos from HTF directional conflict.
6. Remove early prohibited-state returns that incorrectly block lane-aware evaluation.
7. Preserve hard rejection for true execution-timeframe chaos.
8. Add structured result reasons for each stage.
9. Ensure a scalp exception cannot waive missing evidence.
10. Ensure HTF conflict cannot be mislabeled as chaos.

## Tests

- missing mandatory evidence always rejects;
- scalp lane cannot bypass evidence;
- stale data always rejects;
- invalid stop always rejects;
- no target always rejects;
- true local chaos rejects;
- 30m disagreement alone does not become local chaos;
- candidate-specific results differ for candidates from the same strategy;
- no regression in runner restrictions.

## Acceptance criteria

- ERA-like low-geometry candidates cannot pass merely because of lane.
- Valid local scalp candidates reach HTF consequence logic.
- Mandatory evidence has one authoritative enforcement point.
- Rejection reason identifies the exact stage.

---

# Batch 3 — Multi-layer state classification

## Goal

Stop using one canonical state as the sole strategy compatibility authority.

## Tasks

1. Build execution-timeframe classifier.
2. Build setup-timeframe classifier.
3. Preserve existing context/primary-state classifier as context only.
4. Add structural-bias classification.
5. Add independent risk-condition classification.
6. Map strategy requirements to the relevant layer.
7. Allow overlapping states.
8. Add candidate-specific state snapshots.
9. Preserve the shared scan/analyze analysis core.

## Tests

Explicit fixtures for:

- 5m pullback inside 30m uptrend;
- 3m short reversal attempt inside 15m bullish context;
- 5m breakdown attempt inside 1h range;
- 1m momentum expansion during 15m compression;
- local failed breakout while 30m trends;
- local chaos despite clean HTF;
- clean local setup despite mixed HTF.

## Acceptance criteria

- Strategies no longer ask whether one universal state matches.
- Each candidate receives all required state layers.
- Contradictory but realistic states can coexist.
- No lane is inferred from only the broad context state.

---

# Batch 4 — Direction-aware HTF relationship and consequences

## Goal

Classify HTF disagreement precisely and apply consequences instead of blanket vetoes.

## Tasks

1. Add relationship classification:
   - with trend;
   - mixed;
   - countertrend scalp;
   - reversal attempt;
   - structural reversal confirmed.
2. Add severity.
3. Add evidence for confirmed HTF continuation:
   - breakout/reclaim;
   - swing structure;
   - participation;
   - nearby level authority.
4. Define consequence policies by lane.
5. Add target ceilings.
6. Add confirmation escalation.
7. Add runner disablement.
8. Add holding-horizon shortening.
9. Add explicit exit conditions at opposing structure.
10. Keep direct structural opposition as a possible hard rejection.

## Tests

- 5m short against weak 30m bullish bias gets mild penalty;
- 5m short against confirmed 30m long becomes countertrend scalp;
- countertrend scalp has closer target and no runner;
- direct nearby 30m support destroys short reward and rejects;
- aligned setup remains runner eligible;
- reversal attempt is not mislabeled as confirmed reversal.

## Acceptance criteria

- HTF disagreement is visible and direction-aware.
- Scalp validity is separate from runner validity.
- Strong HTF conflict changes management before it changes existence.
- Direct structural opposition can still reject when justified.

---

# Batch 5 — Lane and holding-horizon derivation

## Goal

Derive lanes from setup geometry and lifecycle rather than CMP proximity.

## Tasks

1. Define canonical lane classifier inputs:
   - strategy family;
   - execution timeframe;
   - setup timeframe;
   - invalidation timeframe;
   - target timeframe;
   - ATR-normalized target distance;
   - expected bars to target;
   - current price relation to entry;
   - trigger state;
   - lifecycle model.
2. Separate:
   - CMP scalp;
   - confirmation scalp;
   - pullback scalp;
   - nearby structured;
   - runner;
   - developing.
3. Reclassify candidates at CMP out of nearby.
4. Preserve conditional setups away from CMP.
5. Add holding-horizon categories and bar estimates.
6. Ensure entry mode does not define horizon by itself.

## Tests

- current breakout entry is not automatically a scalp unless horizon supports it;
- nearby pullback scalp stays scalp;
- retest mode does not automatically imply scalp;
- CMP inside zone becomes current/confirmation;
- entry away from CMP stays nearby;
- runner requires broader structural authority.

## Acceptance criteria

- Lane and horizon are explainable from measurable inputs.
- No nearby candidate is exactly at CMP unless a valid reason is explicitly represented.
- Runner cannot be inferred from target count alone.

---

# Batch 6 — Hard geometry safety gate

## Goal

Prevent structurally unacceptable candidates from entering portfolios.

## Tasks

1. Implement direction-aware geometry validation.
2. Implement lane-specific TP1 floors.
3. Implement stop-distance limits by lane.
4. Implement target-quality hard floor.
5. Include expected fees/slippage.
6. Reject internal inconsistency.
7. Add actual-versus-required diagnostics.
8. Apply before portfolio selection.
9. Keep thresholds configuration-driven.
10. Ensure all calculations use canonical selected entry.

## Regression examples

- ERA at 0.21R rejects.
- HEI at 0.18R rejects.
- VANRY at 0.66R rejects.
- CLO at 0.71R rejects unless a validated lane-specific exception exists.
- wrong-side target rejects;
- wrong-side stop rejects;
- stop inside entry zone rejects;
- costs eliminating reward rejects.

## Acceptance criteria

- No displayed valid trade has unacceptable geometry.
- Rejected candidates remain traceable.
- Thresholds are not hardcoded across unrelated strategies.
- JSON and explain output show exact rejection mathematics.

---

# Batch 7 — Entry geometry authority and breakout-retest repair

## Goal

Preserve generator-defined structural entries and stop CMP overwrites.

## Tasks

1. Define canonical entry-geometry ownership.
2. Preserve:
   - zone low;
   - preferred entry;
   - zone high;
   - trigger level;
   - maximum chase;
   - pre-entry invalidation.
3. Repair breakout-retest geometry:
   - breakout level;
   - retest range;
   - penetration allowance;
   - hold/confirmation rule.
4. Recalculate stop and targets from selected entry.
5. Add market-entry label for true single-price immediate entries.
6. Distinguish a collapsed range caused by tick formatting from an actually single-price entry.
7. Verify short maximum chase direction.
8. Ensure serializer and renderer do not alter geometry.

## Tests

- breakout retest away from CMP stays nearby;
- CMP cannot overwrite retest entry;
- nearby candidate at CMP is reclassified;
- R:R uses preferred entry;
- short chase boundary is correct;
- JSON preserves full zone precision;
- CLI formatting does not collapse internal geometry.

## Acceptance criteria

- Strategy-generated geometry survives to final JSON unchanged except explicit canonical normalization.
- Every transformation is traceable.
- CMP is used only when it is truly the selected entry.

---

# Batch 8 — Continuation freshness, extension, and reversal watch

## Goal

Stop late momentum chasing and distinguish continuation from exhaustion.

## Tasks

1. Add impulse-travel measurements.
2. Add objective-consumption measurements.
3. Add remaining-target-room checks.
4. Add VWAP/EMA extension.
5. Add swing-progress and failure detection.
6. Add momentum deceleration.
7. Add wick-recovery and reclaim evidence.
8. Add optional volume/OI continuation evidence.
9. Add continuation-state classification.
10. Route exhausted moves to:
    - no new continuation;
    - scalp only;
    - reversal watch.

## Tests

- fresh breakdown can qualify;
- first continuation can qualify;
- mature continuation is downgraded;
- late chase rejects;
- exhausted short becomes no new short;
- bullish reclaim watch is not an automatic long;
- failed breakdown can create a reversal candidate only after required trigger.

## Acceptance criteria

- “price already dropped heavily” is measurable.
- Continuation decisions incorporate remaining movement, not only past momentum.
- Reversal warnings do not bypass confirmation.

---

# Batch 9 — Execution-quality calculation

## Goal

Make execution quality reflect actual executability.

## Tasks

1. Implement component model.
2. Add hard caps.
3. Separate active-candle status.
4. Include spread/slippage and freshness.
5. Include stop feasibility.
6. Include chase.
7. Include trigger completion.
8. Preserve component breakdown.
9. Remove any implicit equation between ideal-entry proximity and perfect score.

## Tests

- incomplete confirmation cannot exceed cap;
- provisional candle cannot exceed cap;
- outside zone cannot score highly;
- beyond chase rejects;
- perfect location with stale data rejects;
- poor spread reduces execution quality;
- valid completed trigger can score highly.

## Acceptance criteria

- No logical contradiction such as `100/100` with incomplete confirmation.
- Component values explain final score.
- Execution quality is distinct from setup quality.

---

# Batch 10 — Confidence and quality decomposition

## Goal

Remove semantic score conflation.

## Tasks

1. Separate all score dimensions end-to-end.
2. Remove serializer fallback that maps multiple fields from one effective confidence value.
3. Define overall trade quality weighting by lane.
4. Preserve raw component values.
5. Mark uncalibrated pattern confidence as evidence strength, not win probability.
6. Add calibration metadata when available.
7. Update text labels and JSON schema.

## Tests

- high setup/low execution scenario;
- medium confidence/high geometry scenario;
- high alignment/poor reward scenario;
- missing data lowers data confidence only unless hard requirement;
- overall score does not overwrite components;
- JSON fields remain independent.

## Acceptance criteria

- Operator can tell why a setup is good or bad.
- No score is presented as calibrated probability without evidence.
- Hard rejection remains rule-based.

---

# Batch 11 — Target hierarchy and runner qualification

## Goal

Generate meaningful targets and independently qualify runners.

## Tasks

1. Implement target-source hierarchy.
2. Deduplicate by tick size.
3. Enforce direction and ordering.
4. Require TP1.
5. Add TP2/TP3 only when defensible.
6. Add partial-percentage coherence.
7. Add runner authority requirements.
8. Add target basis to diagnostics.
9. Add target-timeframe metadata.
10. Add target ceilings for countertrend scalp.

## Tests

- one valid TP accepted;
- one weak TP rejected;
- duplicate targets removed;
- target ordering enforced;
- countertrend target capped;
- runner denied under HTF opposition;
- runner target only appears after qualification;
- target source preserved in JSON.

## Acceptance criteria

- Renderer displays all real targets.
- No fabricated visual-completeness targets.
- Scalp and runner target logic are independent.

---

# Batch 12 — Portfolio retention and collision handling

## Goal

Retain the best valid opportunity per lane without premature collapse.

## Tasks

1. Preserve all generated candidates.
2. Retain best:
   - CMP scalp;
   - confirmation scalp;
   - pullback scalp;
   - nearby;
   - runner;
   - developing;
   - opposite-direction warning.
3. Define true duplicate geometry.
4. Define true long/short collisions.
5. Do not remove distinct opportunities merely because they share a symbol.
6. Record every suppression reason.
7. Ensure rejected candidates cannot re-enter through legacy setup fields.

## Tests

- two candidates from same strategy receive different results;
- valid different lanes coexist;
- duplicate geometry collapses deterministically;
- opposing simultaneous entries resolve transparently;
- rejected legacy setup cannot leak into portfolio;
- best candidate per lane is deterministic.

## Acceptance criteria

- Valid opportunities survive long enough to be compared correctly.
- No premature strategy-level suppression.
- Collision logic is explainable.

---

# Batch 13 — Ranking

## Goal

Make displayed order a truthful recommendation order.

## Tasks

1. Implement ranking eligibility.
2. Implement deterministic ranking precedence.
3. Add `rank_score`.
4. Add stable tie-breaker.
5. Rank across retained portfolio opportunities.
6. Preserve lane grouping where needed without hiding global quality.
7. Decide whether scan shows:
   - global ranked list with lane labels;
   - or lane groups with rank within each lane.
8. Document the chosen behavior.

## Tests

- better valid setup ranks above weaker setup;
- executable valid setup ranks above nearby setup where intended;
- poor R:R cannot rank highly;
- HTF conflict affects rank but does not necessarily reject;
- stable order on repeated run with same data;
- direction filter changes display only.

## Acceptance criteria

- `#1` truly means top-ranked under documented logic.
- Rank components are visible in explain/JSON.
- Portfolio order is not accidental analysis order.

---

# Batch 14 — CLI and JSON presentation restoration

## Goal

Restore methodology transparency while keeping output compact.

## Tasks

1. Add compact strategy/actionability/state header.
2. Show lane and HTF relationship.
3. Show extension state.
4. Show score dimensions.
5. Show TP1 R:R and target quality.
6. Move raw ID to explain/JSON.
7. Implement adaptive/tick-aware price formatting.
8. Preserve full JSON precision.
9. Ensure scan and analyze use the same opportunity model.
10. Keep empty optional sections hidden.

## Tests

- strategy visible;
- actionability visible;
- methodology state visible;
- no raw ordinal ID in normal card;
- small-price formatting;
- high-price formatting;
- exchange precision cap;
- complete JSON unchanged in authority;
- text output remains readable.

## Acceptance criteria

- Operator can identify what trade is being proposed and why.
- CLI does not imply certainty.
- Display does not alter calculations.

---

# Batch 15 — Configuration and migration

## Goal

Expose methodology thresholds safely and avoid hidden behavior.

## Tasks

1. Add configuration for:
   - lane TP1 floors;
   - stop limits;
   - execution caps;
   - HTF consequence strengths;
   - extension thresholds;
   - target-quality floors;
   - ranking weights.
2. Validate configuration.
3. Add defaults.
4. Add schema documentation.
5. Fail clearly on invalid values.
6. Avoid silent fallback to permissive behavior.
7. Preserve backward compatibility only where safe.

## Tests

- valid config loads;
- invalid thresholds fail;
- missing optional config uses documented defaults;
- no threshold is duplicated in code;
- lane-specific values are respected;
- scan/analyze resolve identical config.

## Acceptance criteria

- Behavior is inspectable and configurable.
- No universal fixed percentage is hidden in strategy code.
- Defaults are conservative.

---

# Batch 16 — Backtest, outcome tracking, and calibration readiness

## Goal

Ensure methodology changes can be evaluated as a versioned edge rather than by isolated anecdotes.

## Tasks

1. Add new fields to backtest decisions.
2. Preserve no-trade and rejected-candidate histories.
3. Record:
   - state layers;
   - relationship;
   - lane;
   - geometry;
   - score components;
   - extension state;
   - target basis;
   - rejection reason.
4. Ensure no look-ahead.
5. Version strategy/methodology definitions.
6. Segment metrics by:
   - strategy;
   - lane;
   - direction;
   - HTF relationship;
   - continuation state;
   - execution state.
7. Prepare calibration reports.
8. Keep outcome tracking compatible.

## Required metrics

- sample size;
- expectancy;
- win rate;
- payoff ratio;
- profit factor;
- drawdown;
- MFE;
- MAE;
- target-hit distribution;
- stop-hit distribution;
- missed-entry rate;
- invalidation rate;
- rule-adherence rate;
- performance by lane;
- performance by HTF relationship;
- calibration reliability.

## Acceptance criteria

- A winning rule violation remains a defect.
- A valid losing trade remains a valid process outcome.
- Threshold tuning is based on samples, not one trade.
- Production and backtest share the same canonical analysis path.

---

# Batch 17 — Full regression and rollout gate

## Goal

Verify the entire pipeline before treating the methodology correction as complete.

## Required regression scenarios

1. Valid aligned CMP scalp.
2. Valid countertrend scalp with constrained target.
3. Direct HTF opposition rejection.
4. Missing mandatory evidence.
5. True local chaos.
6. Broad HTF conflict but clean local structure.
7. Breakout retest away from CMP.
8. Nearby candidate accidentally at CMP.
9. Low R:R rejection.
10. Wrong-side stop.
11. Wrong-side target.
12. Late continuation.
13. Exhaustion reversal watch.
14. Incomplete confirmation score cap.
15. One valid TP.
16. Runner denied.
17. Runner approved.
18. Duplicate collision.
19. Long/short collision.
20. Adaptive price formatting.
21. Scan/analyze parity.
22. Backtest/live decision parity on same closed-candle snapshot.

## Required validation

Run the repository’s established:

- Ruff formatting;
- Ruff checks;
- scoped mypy;
- focused pytest;
- broader relevant pytest;
- CLI help;
- config check;
- JSON serialization;
- scan/analyze smoke validation;
- backtest smoke validation where applicable.

No validation may be claimed as passed without actual terminal output.

## Rollout decision

The methodology correction is ready only when:

- known bad examples are rejected for the correct reason;
- valid local scalps survive HTF classification;
- missing evidence never passes;
- scan/analyze remain canonical-core consistent;
- CLI ranking and labels are truthful;
- JSON remains complete;
- backtest records the new semantics.

---

# 14. Batch dependency order

```text
Batch 0  Baseline evidence
Batch 1  Contracts
Batch 2  Eligibility safety
Batch 3  Layered state
Batch 4  HTF relationship
Batch 5  Lane/horizon
Batch 6  Geometry gate
Batch 7  Entry authority
Batch 8  Extension/reversal protection
Batch 9  Execution quality
Batch 10 Score decomposition
Batch 11 Targets/runner
Batch 12 Portfolio retention
Batch 13 Ranking
Batch 14 CLI/JSON
Batch 15 Configuration
Batch 16 Backtest/calibration
Batch 17 Full regression
```

The order must not be rearranged casually.

In particular:

- do not tune ranking before geometry is safe;
- do not redesign CLI before canonical fields are correct;
- do not loosen thresholds before rejection traces exist;
- do not calibrate before backtest records the new dimensions;
- do not implement runner targets before scalp and HTF classification are separated.

---

# 15. Definition of done for the full plan

The complete fixes plan is done only when Apex satisfies all of the following:

1. Candidate-specific routing remains preserved.
2. Mandatory evidence cannot be bypassed.
3. True execution chaos is distinct from HTF disagreement.
4. Multi-timeframe state is layered rather than collapsed.
5. HTF relationship is direction-aware and severity-aware.
6. Countertrend scalps may survive with constrained management.
7. Direct structural opposition can still reject.
8. Lane and holding horizon are geometry/timeframe-derived.
9. Weak reward trades are rejected before portfolio selection.
10. Entry geometry is not overwritten by CMP.
11. Breakout retests preserve structural zones.
12. Execution quality cannot be perfect with incomplete confirmation.
13. Confidence, setup, execution, reward, timing, and data scores are separate.
14. Late continuation and exhaustion are identified.
15. Targets are structural, ordered, distinct, and non-fabricated.
16. Runner qualification is independent.
17. All candidates remain traceable.
18. One best valid candidate per lane can survive.
19. Collision handling removes only true conflicts/duplicates.
20. CLI order is actual ranking or explicitly non-ranked.
21. CLI restores strategy, state, actionability, lane, and HTF context.
22. Raw candidate IDs remain diagnostic rather than operator-facing.
23. Price formatting is adaptive and tick-aware.
24. Scan and analyze use the same shared analysis authority.
25. Backtest and outcome tracking record the new methodology dimensions.
26. No result is represented as certainty.
27. No trade is fabricated to fill output.
28. No completion or validation claim is made without actual evidence.

---

# 16. Recommended progress reporting during implementation

After every patch report:

```text
Patch completion: X%
Current batch completion: X%
Overall fixes.md completion: X%
Changed files:
Validation requested:
Known remaining risks:
Next safe step:
```

Suggested overall weighting:

| Batch | Weight |
|---|---:|
| 0 | 4% |
| 1 | 5% |
| 2 | 8% |
| 3 | 8% |
| 4 | 8% |
| 5 | 6% |
| 6 | 9% |
| 7 | 7% |
| 8 | 7% |
| 9 | 5% |
| 10 | 5% |
| 11 | 6% |
| 12 | 5% |
| 13 | 4% |
| 14 | 5% |
| 15 | 3% |
| 16 | 3% |
| 17 | 2% |
| **Total** | **100%** |

---

# 17. Final expected operator behavior

A high-quality current opportunity should look like:

```text
Rank #1 BTC/USDT — SHORT
Momentum Scalp · Countertrend scalp · Ready now

CMP                  64,230.50
Entry zone           64,205.00–64,245.00
Preferred entry      64,220.00
Maximum chase        64,170.00
Stop                 64,390.00
TP1                  63,980.00 · 1.41R
TP2                  Not qualified
Runner               Disabled — confirmed 30m bullish continuation

Pattern confidence   76/100
Setup quality        81/100
Execution quality    73/100
Target quality       72/100
HTF alignment        39/100 — strong countertrend
Overall trade quality 70/100

Main risk            30m bullish structure may resume at 64,000–63,950
Holding horizon      5–20 minutes
Exit condition       5m bullish reclaim above local resistance
```

A rejected weak candidate should look like:

```text
ERA/USDT — REJECTED
Breakout Retest Short

Reason               Inadequate target geometry
TP1 reward/risk      0.21R
Required             1.25R for nearby structured setup
Stop distance        6.14%
Target distance      1.31%
Target quality       8.2/100
Rejected at          Geometry safety gate
```

A developing setup should look like:

```text
SOL/USDT — CONDITIONAL LONG SCALP
VWAP Reclaim · Confirmation required

Trigger              3m close above 153.86
Entry zone           153.86–154.05
Preferred entry      153.92
Maximum chase        154.18
Stop                 153.21
TP1                  154.74 · 1.18R
TP2                  155.38 · 2.07R
Runner               Not qualified
Expiry               6 × 3m candles
Invalid before entry 3m close below 153.21
Why not now          Reclaim confirmation is incomplete
Order intent         Alert only
```

This is the target behavior: more valid trades retained, fewer false positives, no forced trades, no hidden evidence bypass, and complete operator context.