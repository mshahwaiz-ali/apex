Apex Trading Project
Future-Setup Preservation and Backtest Parity Implementation Plan
=================================================================

Purpose
-------

Fix the current architecture so that a valid trade setup is never converted into NO_TRADE merely because entry is not available at CMP.

NO_TRADE must be returned only when no structurally valid trade setup exists.

The same canonical trade-analysis engine must drive:

- apex scan
- apex analyze SYMBOL
- apex backtest

The three commands may differ in presentation and replay behavior, but they must use the same strategy candidates, setup validity, entry plans, stop plans, target plans, timeframe relationships, and execution rules.


Core Product Rule
-----------------

Apex must answer three separate questions:

1. Is there a valid trade thesis?
2. Is entry available now at CMP?
3. If not available now, what exact future trigger would make the setup executable?

A negative answer to question 2 must not erase a positive answer to question 1.

Correct behavior:

- Valid setup + entry available now:
  READY_NOW or AGGRESSIVE_NOW

- Valid setup + entry not available now:
  FUTURE_TRIGGER / CONDITIONAL_FUTURE

- Valid setup + primary entry missed but re-entry remains structurally valid:
  MISSED_PRIMARY_ENTRY_WITH_REENTRY

- No structurally valid setup:
  NO_TRADE

- Setup structurally invalidated:
  INVALIDATED


Target Canonical State Model
----------------------------

A. Setup validity

- VALID
- INVALID
- EXPIRED

B. Entry availability

- READY_NOW
- AGGRESSIVE_NOW
- CONFIRMATION_AT_CMP
- PULLBACK_PENDING
- RETEST_PENDING
- RECLAIM_PENDING
- BREAKOUT_PENDING
- WATCH_NEAR_ENTRY
- MISSED_PRIMARY_ENTRY
- INVALIDATED

C. Execution authority

- EXECUTE_NOW
- CONDITIONAL_FUTURE
- MONITOR_ONLY
- PROHIBITED

D. Setup lifecycle

- DETECTED
- WAITING_FOR_TRIGGER
- ACTIVATED
- FILLED
- TARGET
- STOP
- TIME_EXIT
- PRE_ENTRY_INVALIDATED
- ACTIVATION_EXPIRED
- MISSED_TRIGGER


Architectural Principle
-----------------------

Entry geometry is descriptive and execution-authoritative, but it is not allowed to destroy a valid setup.

Entry logic must determine:

- current entry availability
- future entry zone
- ideal entry
- trigger type
- trigger level
- trigger confirmation timeframe
- maximum chase
- setup expiry
- pre-entry invalidation
- stop after activation
- targets after activation

Entry logic must not answer whether the trade thesis exists. That remains the responsibility of strategy, regime, structure, methodology, and risk validity.


Current Confirmed Defects
-------------------------

1. Valid nearby entry references can disappear before scoring

Current entry-zone logic may reject a reference because:

- it is beyond the configured immediate distance
- it does not improve R:R over CMP by the configured percentage
- it is not currently reachable inside immediate geometry
- it lies outside the current entry horizon

This is incorrect for one-shot scan/analyze behavior.

Required change:

- preserve structurally valid references
- classify them by horizon and actionability
- use distance and R:R improvement for ranking, not setup deletion
- reject only impossible or structurally invalid geometry


2. Current execution status blocks final setup selection

Current final selection effectively requires an executable-now status.

This converts:

- pullback pending
- retest pending
- reclaim pending
- confirmation pending
- breakout pending
- valid nearby structured setup

into a final no-trade result.

Required change:

Selection must return two separate authorities:

- selected_executable_candidate
- selected_future_candidate

If no executable candidate exists but a valid future candidate exists, the future candidate becomes the authoritative setup.


3. Conditional plans are secondary instead of canonical

The code already supports concepts such as:

- price-touch trigger
- retest-hold trigger
- reclaim-close trigger
- candle-close trigger
- pre-entry invalidation
- confirmation timeframe
- recommended order intent

Required change:

Conditional plans must become first-class canonical trade opportunities, not optional developing diagnostics.


4. Backtest shadow replay is not equivalent to production replay

Current shadow replay may simulate geometry-rejected candidates as immediate fills.

This can produce apparent wins and losses that do not correspond to the actual canonical execution path.

Required change:

- do not immediate-fill future or geometry-rejected setups
- register the setup at the decision candle
- wait chronologically for its trigger
- activate only after the planned trigger
- reject if invalidated before activation
- expire if trigger window closes
- simulate SL and targets only after fill


5. Strategy generation is still too dependent on ordinary HTF disagreement

Multiple strategy families can be eliminated together due to:

- momentum mismatch
- higher-timeframe contradiction

Required change:

Only decisive direct structural opposition should hard-reject a setup.

Mild or moderate HTF disagreement should result in:

- score penalty
- shorter holding horizon
- target ceiling
- runner disabled
- reduced confidence
- stricter expiry

It should not automatically erase a valid scalp or near-term setup.


6. Timeframe indicator profiles remain insufficiently differentiated

1m and 3m have distinct profiles, but 5m through 4h remain mostly similar.

Required change:

Create explicit profiles for:

- 1m timing
- 3m refinement
- 5m execution
- 15m setup
- 30m intraday structure
- 1h intermediate trend
- 4h macro regime

Each profile must have its own indicator periods and role-specific interpretation.


Implementation Batches
======================

Batch 1 — Preserve All Structurally Valid Entry Opportunities
------------------------------------------------------------

Primary areas:

- src/apex/strategies/entry.py
- entry contracts
- entry selection tests
- strategy candidate construction tests

Required changes:

1. Replace destructive filtering with classification.

Every candidate entry reference must be classified as one of:

- IMMEDIATE
- NEARBY
- FUTURE_TRIGGER
- OUTSIDE_HORIZON
- STRUCTURALLY_INVALID

2. Distance rules must change behavior.

Current distance limits should determine:

- whether the setup is immediate
- whether it belongs to near-term future horizon
- whether it is too far to be useful in this scan

They must not delete a structurally valid setup.

3. R:R improvement must become a ranking factor.

A future reference should not disappear merely because it improves R:R by less than the current configured threshold.

The engine should retain:

- CMP entry
- strategy entry
- pullback entry
- retest entry
- reclaim entry
- breakout trigger entry

Then rank them by:

- structural quality
- net R:R
- distance
- entry freshness
- confirmation quality
- target room
- stop quality

4. Preserve market and future entries together.

The candidate should be able to contain:

- current executable entry
- preferred future entry
- alternative valid re-entry opportunities

5. Keep hard safety rejections.

Still reject:

- long entry at or below invalidation
- long entry at or beyond target
- short entry at or above invalidation
- short entry at or beyond target
- non-finite prices
- non-positive prices
- impossible stop/target ordering
- invalid maximum-chase direction
- structurally impossible geometry

Deliverables:

- updated entry classification
- updated entry opportunity contract
- regression tests
- no change to unrelated strategy behavior


Batch 2 — Separate Setup Validity from Current Executability
-----------------------------------------------------------

Primary areas:

- src/apex/scoring/selection.py
- candidate selection contracts
- discovery assessment construction
- selection tests

Required changes:

1. Extend selection result.

Add:

- selected_executable_candidate
- selected_future_candidate
- selected_monitor_candidate
- setup_exists

2. Selection precedence.

Use this order:

a. best valid executable-now candidate
b. best valid future-trigger candidate
c. best valid monitor-only re-entry candidate
d. NO_TRADE only if none exists

3. Replace misleading no-trade result.

Current behavior:

valid setup exists, but none has a currently executable entry
=> NO_TRADE

New behavior:

valid setup exists, entry pending
=> FUTURE_SETUP

4. Keep candidate outcome and execution status separate.

Candidate acceptance answers:

- is the trade setup valid?

Entry status answers:

- can it be entered now?

These must remain independent.

5. Add explicit reason codes.

Examples:

- VALID_SETUP_EXECUTABLE_NOW
- VALID_SETUP_PENDING_PULLBACK
- VALID_SETUP_PENDING_RETEST
- VALID_SETUP_PENDING_RECLAIM
- VALID_SETUP_PENDING_BREAKOUT
- VALID_SETUP_MISSED_PRIMARY_REENTRY_AVAILABLE
- NO_VALID_SETUP
- SETUP_INVALIDATED
- SETUP_OUTSIDE_SUPPORTED_HORIZON

Deliverables:

- revised selection contract
- revised no-trade semantics
- exhaustive precedence tests


Batch 3 — Promote Future Setup to a First-Class Canonical Contract
-----------------------------------------------------------------

Primary areas:

- discovery contracts
- src/apex/application/discovery_setup.py
- opportunity portfolio contracts
- serialization
- CLI view models
- contract tests

Required canonical fields:

- setup_valid
- execution_allowed_now
- future_activation_allowed
- setup_state
- entry_state
- execution_authority
- activation_trigger
- activation_level
- activation_zone
- activation_confirmation_timeframe
- activation_expiry_bars
- activation_expiry_seconds
- pre_entry_invalidation
- maximum_chase
- planned_stop_after_activation
- planned_targets_after_activation
- management_plan
- runner_qualified
- runner_reason
- strategy_version
- methodology_version
- decision_timestamp

Rules:

- a future setup must include complete entry, stop, and target geometry
- it must not claim execution at CMP
- it must state exactly what activates it
- it must state what invalidates it before activation
- it must state how long it remains valid

Deliverables:

- canonical future-setup object
- serialization compatibility
- contract tests


Batch 4 — Implement Correct Chronological Trigger Replay
-------------------------------------------------------

Primary areas:

- backtest chronological replay
- signal mapping
- activation engine
- trade simulator
- backtest contracts
- lifecycle tests

Required behavior:

1. At decision time:

- generate the canonical setup
- freeze the setup snapshot
- register future activation plan

2. For every subsequent candle:

- test pre-entry invalidation first
- test expiry
- test activation trigger
- apply deterministic same-candle ordering rules
- fill only after trigger conditions are satisfied

3. Supported triggers:

- PRICE_TOUCH
- CANDLE_CLOSE
- RETEST_HOLD
- RECLAIM_CLOSE
- BREAKOUT_CLOSE
- MOMENTUM_RENEWAL

4. Fill modeling:

- use planned entry geometry
- use trigger-relative fill
- include configured slippage
- include fees
- respect maximum chase
- do not use arbitrary CMP fill
- do not rebuild entry from future data

5. Pre-entry terminal states:

- PRE_ENTRY_INVALIDATED
- ACTIVATION_EXPIRED
- MISSED_TRIGGER
- NEVER_ACTIVATED

6. Post-entry terminal states:

- TARGET
- STOP
- TIME_EXIT
- PARTIAL_TARGET_THEN_STOP
- PARTIAL_TARGET_THEN_TIME_EXIT

Deliverables:

- canonical activation replay engine
- deterministic event ordering
- no-look-ahead tests
- same-candle ambiguity tests
- trigger-specific tests


Batch 5 — Remove Shadow/Production Replay Confusion
--------------------------------------------------

Primary areas:

- backtest reports
- metrics aggregation
- calibration records
- CLI output
- JSON output

Required result layers:

A. Canonical production replay

Only setups that were valid under the canonical engine.

B. Conditional setup replay

Valid future setups that activated or expired chronologically.

C. Research shadow replay

Rejected or counterfactual candidates used only for diagnostics.

Reporting rules:

- never combine shadow results with canonical win rate
- never promote shadow trades into calibration authority
- show source distribution clearly
- label every trade with replay source
- calibration uses canonical filled trades only

Required source values:

- retained_executable
- retained_future_activated
- retained_future_expired
- retained_future_invalidated
- rejected_shadow
- geometry_shadow
- methodology_shadow

Deliverables:

- clean metric separation
- corrected win/loss ratio reporting
- calibration authority based on canonical trades only


Batch 6 — Correct HTF Conflict Consequences
------------------------------------------

Primary areas:

- strategy routing
- layered methodology state
- strategy candidate generation
- HTF contradiction evaluation
- runner qualification
- target ceilings
- strategy tests

Required severity levels:

- NONE
- MILD
- MODERATE
- STRONG
- CRITICAL

Required consequences:

NONE:
- normal setup

MILD:
- small score penalty

MODERATE:
- score penalty
- runner disabled or constrained
- reduced target horizon

STRONG:
- conditional future setup only
- stricter trigger
- shorter expiry
- no runner

CRITICAL:
- hard rejection

Hard rejection should require direct structural opposition, not ordinary disagreement.

Scalp rule:

A valid 1m/3m/5m scalp may survive 30m/1h disagreement when:

- the local structure is coherent
- stop is tight and structural
- target is nearby
- runner is disabled
- expiry is short
- contradiction is not critical

Deliverables:

- severity-aware HTF routing
- strategy-family regression tests
- no blanket family-wide rejection for ordinary conflict


Batch 7 — Complete Timeframe-Specific Indicator Profiles
--------------------------------------------------------

Primary areas:

- config/default.yaml
- timeframe profile resolver
- market environment analysis
- indicators
- tests

Required profiles:

1m timing:
- fast reaction
- short momentum windows
- micro volume sensitivity

3m refinement:
- slightly slower confirmation
- noise reduction

5m execution:
- execution-quality balance
- breakout and pullback timing

15m setup:
- setup structure
- trend continuation and reversal context

30m intraday:
- directional intraday structure
- support/resistance relevance

1h intermediate:
- trend authority
- volatility regime

4h macro:
- broad regime
- structural bias
- exhaustion and major opposition

Rules:

- do not use one identical indicator interpretation across all timeframes
- timeframe role determines indicator meaning
- profile changes must be config-driven
- backtest, scan, and analyze must use the same profiles

Deliverables:

- role-specific profiles
- resolver tests
- configuration validation tests


Batch 8 — Unify Scan, Analyze, and Backtest
------------------------------------------

Primary areas:

- shared analysis authority
- scan application flow
- analyze application flow
- backtest decision flow
- integration tests

Required invariant:

Given the same symbol, timestamp, market data, configuration, and methodology version:

- scan
- analyze
- backtest decision generation

must create the same canonical setup object.

Allowed differences:

scan:
- symbol discovery
- concise ranking
- multiple symbols

analyze:
- one symbol
- full diagnostics

backtest:
- historical timestamps
- chronological future replay

Not allowed:

- different strategy logic
- different entry geometry
- different stop/target generation
- different HTF routing
- different setup-validity rules
- backtest-only reconstructed signals

Deliverables:

- canonical parity tests
- serialized setup snapshot comparison
- same dataset/same timestamp consistency tests


Batch 9 — Redesign CLI Semantics
--------------------------------

Apex scan output order per symbol:

1. EXECUTABLE NOW
2. FUTURE SETUP
3. MISSED PRIMARY / RE-ENTRY AVAILABLE
4. MONITOR ONLY
5. NO VALID SETUP

Future setup output must include:

- CMP
- direction
- strategy
- entry zone
- ideal entry
- trigger type
- trigger price
- confirmation timeframe
- maximum chase
- pre-entry invalidation
- setup expiry
- stop after activation
- targets
- order intent
- reason not executable now

Example:

Rank #2  SYMBOL/USDT — LONG FUTURE SETUP

Status
  Valid setup
  Entry not available at CMP

CMP
  1.2500

Activation
  Entry zone              1.2280 - 1.2340
  Ideal entry             1.2310
  Trigger                 5m retest hold
  Maximum chase           1.2380
  Pre-entry invalidation  1.2180
  Expiry                  6 x 5m candles

Risk after activation
  Stop loss               1.2140

Targets
  TP1                     1.2580
  TP2                     1.2810

Action
  Do not enter at CMP.
  Setup becomes executable only after the planned trigger.

Deliverables:

- scan renderer
- analyze renderer
- backtest report renderer
- output snapshot tests


Batch 10 — Calibration and Backtest Acceptance Criteria
-------------------------------------------------------

Do not tune for win rate until the canonical trade population is correct.

Required metrics:

- valid setup count
- executable-now setup count
- future setup count
- activation count
- activation rate
- pre-entry invalidation count
- expiry count
- actual filled trades
- target exits
- stop exits
- time exits
- win rate
- expectancy in R
- profit factor
- average win
- average loss
- maximum drawdown
- MAE
- MFE
- performance by timeframe
- performance by strategy
- performance by HTF severity
- performance by entry trigger
- performance by replay source

Minimum evaluation guidance:

- 30 to 50 canonical filled trades per lane/timeframe before early tuning
- 100 or more combined out-of-sample canonical trades before any meaningful performance claim
- shadow replay excluded from calibration
- immutable strategy/config version per sample
- rule changes start a new sample version


Testing Plan
============

Unit tests
----------

Entry:

- valid future reference is preserved
- R:R improvement affects ranking, not eligibility
- outside-immediate-distance reference becomes future setup
- structurally invalid reference is rejected
- max chase remains directionally valid
- market and future entries coexist

Selection:

- executable candidate wins over future candidate
- future candidate wins over monitor-only candidate
- future candidate prevents NO_TRADE
- NO_TRADE occurs only with no valid setup
- invalidated candidate cannot become future setup

Conditional plans:

- price-touch trigger
- retest-hold trigger
- reclaim-close trigger
- breakout-close trigger
- momentum-renewal trigger
- pre-entry invalidation
- expiry

Backtest:

- setup snapshot frozen at decision time
- no look-ahead
- trigger happens before fill
- invalidation before trigger prevents fill
- expiry prevents late fill
- maximum chase prevents chased fill
- fees and slippage applied
- same-candle ambiguity deterministic
- partial-target lifecycle correct

HTF:

- mild conflict does not hard-reject
- moderate conflict disables runner
- strong conflict forces conditional setup
- critical direct opposition rejects
- scalp survives non-critical HTF disagreement

Parity:

- scan/analyze/backtest produce identical setup snapshot
- same config produces deterministic result
- strategy version and methodology version recorded


Integration validation
----------------------

After every implementation batch:

1. Ruff format changed files
2. Ruff check changed files --fix
3. Ruff check changed files
4. scoped mypy
5. relevant pytest
6. focused CLI smoke command
7. targeted backtest sample
8. inspect JSON and rendered output

Never claim validation passed unless actual terminal output is provided.


Recommended Implementation Order
================================

Phase 1 foundation:

- Batch 1
- Batch 2

Goal:
A valid setup survives even when entry is not available at CMP.

Phase 2 lifecycle:

- Batch 3
- Batch 4
- Batch 5

Goal:
Future setup becomes canonical and backtest activates it chronologically.

Phase 3 methodology quality:

- Batch 6
- Batch 7

Goal:
Remove blanket HTF suppression and complete timeframe-specific behavior.

Phase 4 parity and presentation:

- Batch 8
- Batch 9

Goal:
Scan, analyze, and backtest use the same authority and clearly display future setups.

Phase 5 calibration:

- Batch 10

Goal:
Evaluate real canonical trade performance only after the trade population is correct.


Definition of Done
==================

The implementation is complete when all of the following are true:

1. A valid future setup never becomes NO_TRADE only because entry is unavailable at CMP.

2. NO_TRADE means no valid trade setup exists.

3. One scan provides:

- immediate entry if available
- future entry plan if not
- trigger
- expiry
- pre-entry invalidation
- stop
- targets
- maximum chase

4. Backtest waits for the same future trigger that scan/analyze displayed.

5. Backtest does not arbitrary-fill a future setup at CMP.

6. Backtest does not rebuild a setup using future data.

7. Pre-entry invalidation and expiry are simulated.

8. Shadow results are excluded from canonical performance metrics.

9. Ordinary HTF disagreement does not kill every scalp or short-horizon setup.

10. 1m, 3m, 5m, 15m, 30m, 1h, and 4h use role-specific profiles.

11. Scan, analyze, and backtest produce the same canonical trade setup for identical inputs.

12. Win rate and calibration are reported only from canonical filled trades.


First Implementation Batch
==========================

Start with Batch 1 and Batch 2 as one coherent patch:

- preserve structurally valid future entry opportunities
- stop using R:R improvement as a destructive eligibility gate
- classify future horizon instead of deleting references
- separate setup acceptance from immediate executability
- add selected_future_candidate
- return NO_TRADE only when no valid setup exists
- add regression tests for all new precedence rules

After this patch is validated, proceed to Batch 3 and Batch 4.