WARNING DONOT READ.
ONLY IMPLEMENT AFTER APEX IS FULLY DONE. 

# Apex Trading Agent — Codex Continuation and Completion Prompt

You are continuing development of the private GitHub repository:

* Repository: `mshahwaiz-ali/apex`
* Default and working branch: `main`
* Primary project specification: `docs/modification.md`
* Language/runtime: Python 3.11+
* CLI: Typer
* Validation/contracts: Pydantic v2
* Configuration: YAML
* Quality tools: Ruff, strict mypy, pytest

## Core instruction

Read `docs/modification.md` completely before making changes.

Treat it as the authoritative product and architecture specification. It supersedes older generic roadmap assumptions where they conflict.

Continue from the repository's current implementation state described below and complete the remaining roadmap safely.

Do not rewrite the whole project unnecessarily. Preserve working market-data, feature, strategy, scoring, risk, scanner, backtesting, paper-trading, intelligence, and execution foundations unless a change is explicitly required by `docs/modification.md`.

---

# Product direction

Apex is a high-risk, high-reward crypto perpetual-futures analysis system.

It must:

* operate in perpetual-futures mode
* use isolated margin only
* support high leverage intentionally
* avoid full-wallet exposure
* provide actionable setups near the current market price
* distinguish precise entry states rather than repeatedly returning vague confirmation advice
* support normal-market opportunities and fast-moving gainers separately
* provide account-aware leverage, margin, loss, liquidation, target, and lifecycle planning
* remain deterministic and testable
* avoid pretending that high leverage guarantees profit
* preserve strict exposure and liquidation controls

Preferred leverage is generally in the 10x–20x range where market structure permits it, with profile-specific limits and lower or higher values where justified.

---

# Work already completed

Do not duplicate these changes. Inspect and build on them.

## Futures product contracts

The repository now contains provider-independent futures contracts under:

* `src/apex/domain/futures.py`
* public exports in `src/apex/domain/__init__.py`

Implemented concepts include:

* `MarginMode.ISOLATED`
* `LeverageMode.AUTOMATIC`
* `LeverageMode.MANUAL`
* `RiskMode.STANDARD`
* `RiskMode.AGGRESSIVE`
* `RiskMode.EXTREME`
* `FuturesDirection.LONG`
* `FuturesDirection.SHORT`
* `EntryState`
* `TradeLifecycleState`
* `FuturesAccountInput`
* `EntryPlan`
* `StopPlan`
* `TargetLeg`
* `TargetPlan`
* `PositionPlan`

Entry geometry is direction-aware for both long and short setups.

## Futures product configuration

Implemented:

* `src/apex/config/futures.py`
* `config/futures.yaml`
* public exports through `src/apex/config/__init__.py`

The configuration defines:

* futures-only behavior
* isolated margin
* default leverage mode
* default risk mode
* risk-mode-specific loss percentages
* minimum, preferred, and maximum leverage
* maximum wallet exposure

## Account input resolver

Implemented:

* `src/apex/application/futures_account.py`
* public application exports

The resolver builds validated `FuturesAccountInput` values from CLI-compatible inputs and product defaults.

## CLI futures account inputs

The `apex analyze` command supports:

* `--wallet-balance`
* `--risk-mode`
* `--leverage-mode`
* `--manual-leverage`
* `--max-account-loss-pct`

The command exposes the resolved futures account in JSON output and prints an account summary in text output.

## Futures-plan mapping

Implemented:

* `src/apex/application/futures_plan.py`

Approved existing risk setups are mapped into:

* entry plan
* stop plan
* target plan
* position plan
* initial lifecycle snapshot

The futures plan is added to analysis output without removing the existing analysis payload.

## Account safety enforcement

Futures plans are checked against the selected account profile.

Current checks include:

* maximum leverage
* minimum manual leverage
* maximum wallet exposure
* maximum planned account loss
* isolated-margin enforcement

Unsafe account geometry returns:

```json
{
  "status": "REJECTED",
  "reasons": [...]
}
```

The underlying market analysis is still preserved.

## Futures lifecycle

Implemented immutable lifecycle contracts and transition rules.

States include:

* `GENERATED`
* `WAITING_FOR_ENTRY`
* `ENTERED`
* `PARTIALLY_CLOSED`
* `STOPPED`
* `TARGET_HIT`
* `EXPIRED`
* `CANCELLED`
* `INVALIDATED`

Lifecycle transitions enforce:

* timezone-aware timestamps
* non-decreasing time
* terminal-state locking
* valid partial-close percentages
* non-decreasing closed percentage
* entered and closed timestamps
* immutable snapshots

Every approved futures plan starts with a deterministic `GENERATED` lifecycle snapshot.

## Existing tests

Tests already exist for:

* futures contracts
* futures configuration
* account input resolution
* futures-plan mapping
* safety rejections
* lifecycle transitions

Inspect existing tests and update them where required. Do not remove useful coverage.

---

# Immediate next task

Implement the entry-state classification engine.

The current implementation mostly distinguishes only:

* `READY_NOW`
* `APPROACHING_ENTRY`

Replace this simplistic mapping with a deterministic, direction-aware classifier.

The classifier must support:

* `WATCH`
* `APPROACHING_ENTRY`
* `READY_NOW`
* `WAIT_FOR_RECLAIM`
* `WAIT_FOR_RETEST`
* `MISSED_ENTRY`
* `INVALIDATED`
* `NO_TRADE`

## Long-state geometry

At minimum, classify long setups using these ideas:

* current price inside the valid entry zone:

  * `READY_NOW`
* price below the entry zone but approaching it without structural failure:

  * `APPROACHING_ENTRY`
* price below a lost trigger or reclaim level but structure is not fully invalidated:

  * `WAIT_FOR_RECLAIM`
* price has moved above the entry zone but remains within the maximum chase boundary and a retest is preferable:

  * `WAIT_FOR_RETEST`
* price is above the maximum chase boundary:

  * `MISSED_ENTRY`
* price is at or below structural invalidation:

  * `INVALIDATED`
* insufficient geometry or rejected market setup:

  * `NO_TRADE`

## Short-state geometry

Invert the logic correctly:

* inside entry zone:

  * `READY_NOW`
* above zone and approaching:

  * `APPROACHING_ENTRY`
* above a lost trigger and waiting for bearish reclaim:

  * `WAIT_FOR_RECLAIM`
* below the zone but still inside the valid chase boundary and waiting for retest:

  * `WAIT_FOR_RETEST`
* below the short chase boundary:

  * `MISSED_ENTRY`
* at or above structural invalidation:

  * `INVALIDATED`

Do not encode ambiguous discretionary logic in random conditionals.

Create a small, explicit classification contract with documented precedence.

Recommended precedence:

1. invalidated
2. missed entry
3. ready now
4. wait for retest
5. wait for reclaim
6. approaching entry
7. watch
8. no trade

Add exhaustive tests for long and short state boundaries.

Expose the classified state in:

* futures-plan JSON
* concise CLI text output
* scanner serialization where relevant

---

# Remaining implementation roadmap

After entry-state classification, continue through the following phases in order unless repository inspection reveals a necessary dependency adjustment.

---

## Phase 2 — Rewrite leverage and margin geometry

The current risk engine was originally designed around lower leverage and generic risk assumptions. Rewrite the futures leverage and margin layer to match `docs/modification.md`.

### Required behavior

Position sizing must begin from:

* wallet balance
* allowed account loss
* entry price
* structural stop distance
* estimated fees
* estimated slippage
* selected leverage mode
* risk profile
* wallet exposure ceiling
* liquidation safety distance

Core calculations must include:

```text
allowed_loss =
    wallet_balance
    × maximum_account_loss_percentage / 100
```

```text
stop_distance =
    abs(entry_price - structural_stop)
```

```text
quantity_by_risk =
    allowed_loss / stop_distance
```

```text
position_notional =
    quantity × entry_price
```

```text
required_margin =
    position_notional / leverage
```

```text
wallet_exposure_percentage =
    required_margin / wallet_balance × 100
```

Account for:

* estimated entry and exit fees
* slippage
* stop execution loss
* liquidation buffer
* maintenance margin assumptions

### Automatic leverage

Automatic leverage selection should:

* prefer the configured profile leverage
* stay within exchange/model limits
* respect wallet exposure
* keep liquidation beyond emergency invalidation with a buffer
* reduce leverage when liquidation proximity becomes unsafe
* reject the plan if no valid leverage exists

### Manual leverage

Manual leverage should:

* validate against selected profile limits
* validate liquidation safety
* validate wallet exposure
* validate planned loss
* never silently adjust the user-selected leverage
* return explicit rejection reasons when unsafe

### Required outputs

Position plan should expose at least:

* selected leverage
* position quantity
* position notional
* required isolated margin
* wallet exposure percentage
* gross risk amount
* fee allowance
* slippage allowance
* maximum planned loss
* estimated liquidation price
* stop-to-liquidation buffer
* reason for selected leverage
* any limiting constraint

Remove placeholder zero fee/slippage values once real modeled values are available.

Add unit tests for all calculations and boundary cases.

---

## Phase 3 — Separate normal-market and gainer scanners

Do not treat ordinary coins and explosive gainers as the same opportunity type.

Introduce separate scanner paths.

### Normal-market scanner

Designed for:

* liquid perpetual pairs
* normal volatility
* trend continuation
* pullbacks
* breakouts
* liquidity sweeps
* mean reversion where appropriate

### Gainer scanner

Designed for:

* rapid price expansion
* volume spikes
* abnormal range expansion
* fast momentum
* newly activated or highly active perpetual pairs
* blow-off risk
* late-entry traps
* squeeze continuation
* failure and reversal setups

### Shared scanner requirements

Both scanners should produce normalized opportunity records containing:

* symbol
* scanner type
* current price
* market regime
* volatility regime
* liquidity quality
* trend direction
* momentum state
* volume state
* extension state
* trap risk
* candidate strategy types
* entry-state summary
* score
* rejection reason when filtered

Do not merge the universes before classification.

Add separate CLI commands or scanner modes with clear output.

---

## Phase 4 — Gainer state machine

Build a deterministic gainer lifecycle.

Suggested states:

* `DISCOVERED`
* `EARLY_EXPANSION`
* `MOMENTUM_CONTINUATION`
* `FIRST_PULLBACK`
* `RETEST`
* `SQUEEZE`
* `OVEREXTENDED`
* `BLOW_OFF`
* `FAILED_BREAKOUT`
* `REVERSAL_CONFIRMING`
* `EXHAUSTED`
* `INVALIDATED`

The state machine should use measurable inputs such as:

* percentage move over multiple windows
* relative volume
* candle-range expansion
* distance from VWAP
* distance from fast and slow EMA
* pullback depth
* reclaim behavior
* wick and rejection behavior
* open-interest change where available
* funding where available
* taker imbalance where available
* liquidation activity where available
* time since initial expansion

Do not label every strong mover as immediately shortable.

Distinguish:

* continuation opportunities
* first-pullback opportunities
* squeeze risk
* exhaustion
* failed breakout
* confirmed reversal

Add state-transition tests and frozen fixtures.

---

## Phase 5 — Precision-entry engine

Create a dedicated precision-entry layer above generic strategy candidates.

The goal is to identify the best actionable entry near current price without always waiting for excessive confirmation.

### Entry components

Use combinations of:

* market structure
* liquidity sweeps
* reclaim levels
* retest levels
* local support/resistance
* VWAP
* EMA alignment
* ATR-adjusted distance
* candle rejection
* volume behavior
* momentum continuation
* momentum failure
* current-price extension
* maximum chase distance
* spread and slippage
* liquidation clusters where available

### Required outputs

Every candidate should include:

* exact entry state
* entry-zone low
* entry-zone high
* ideal entry
* current-price distance from ideal
* maximum chase price
* reclaim trigger
* retest trigger
* invalidation level
* entry-quality score
* adverse-excursion risk score
* trap-risk score
* expected time-to-entry category
* reason the setup is actionable now or not

### Entry quality

Create an explicit score, not a vague confidence reuse.

Potential score groups:

* structural quality
* liquidity quality
* momentum alignment
* volatility suitability
* distance from ideal entry
* extension penalty
* trap penalty
* spread/slippage penalty
* multi-timeframe agreement

Keep scoring deterministic and configuration-driven.

---

## Phase 6 — Strategy and regime routing

Ensure strategies are enabled only in suitable regimes.

Potential strategies include:

* trend pullback
* breakout continuation
* liquidity sweep reversal
* failed breakout
* range mean reversion
* momentum scalp
* first-pullback gainer continuation
* gainer exhaustion reversal
* squeeze continuation
* reclaim entry
* retest entry

Create a routing matrix based on:

* higher-timeframe regime
* execution-timeframe regime
* volatility state
* liquidity state
* gainer state
* extension state
* directional alignment
* trap risk

The router should:

* enable suitable strategies
* disable unsuitable strategies
* assign strategy-specific score adjustments
* explain why a strategy was selected or rejected

Avoid running every strategy on every market condition.

Add table-driven tests.

---

## Phase 7 — Scalp and runner lifecycle

Separate fast profit realization from runner management.

### Target structure

Support configurable target legs such as:

* TP1 scalp
* TP2 continuation
* runner allocation

Target percentages must total 100%.

### Lifecycle behavior

Implement rules for:

* entry fill
* partial fill if applicable
* TP1 hit
* stop movement after TP1
* breakeven logic
* TP2 hit
* runner activation
* trailing stop
* momentum-failure exit
* time-based exit
* structural invalidation
* emergency stop
* full target hit
* stop-out
* expiry

Do not force the same management model on every strategy.

Management policy should depend on:

* strategy
* volatility
* regime
* leverage
* target distance
* confidence
* gainer state

Integrate this lifecycle with paper trading after the contracts are stable.

---

## Phase 8 — Dataset and feature capture

Create structured datasets for:

* raw candles
* normalized candles
* ticker data
* funding
* open interest
* spreads
* order-book summaries if available
* calculated features
* market regime
* scanner classification
* gainer state
* strategy candidates
* scores
* selected setup
* entry state
* account plan
* lifecycle outcomes

Every stored analysis should include:

* configuration identifiers
* code/version metadata where practical
* timestamps
* provider
* symbol
* timeframe
* data-quality indicators

Keep storage provider-independent.

Prefer lightweight local storage appropriate for a Python project unless `docs/modification.md` explicitly requires otherwise.

Do not introduce Frappe unless it clearly improves this standalone trading system. A simple SQLite/Parquet/JSONL approach is likely more appropriate for local research and backtesting.

---

## Phase 9 — Backtesting rewrite

The backtester must exercise the actual production analysis pipeline, not a simplified unrelated strategy.

### Requirements

* strictly chronological data
* no future leakage
* only closed candles for decisions
* realistic entry-state handling
* order expiry
* entry-zone fills
* maximum chase enforcement
* fees
* slippage
* leverage
* isolated margin
* liquidation
* partial targets
* stop transitions
* trailing exits
* time exits
* lifecycle events
* scanner type
* gainer state
* strategy routing

### Metrics

Report at least:

* total trades
* win rate
* loss rate
* breakeven rate
* expectancy
* profit factor
* average R
* median R
* maximum drawdown
* consecutive losses
* return on wallet
* return on margin
* liquidation count
* stop-out count
* target-hit count
* partial-win count
* average adverse excursion
* average favorable excursion
* average entry delay
* missed-entry rate
* invalidation-before-entry rate
* performance by strategy
* performance by regime
* performance by scanner type
* performance by risk mode
* performance by leverage bucket
* performance by entry state
* performance by symbol

Add deterministic fixtures and regression tests.

---

## Phase 10 — Calibration and optimization

Do not optimize solely for raw profit.

Calibrate using robust objectives such as:

* expectancy
* profit factor
* drawdown
* liquidation rate
* trade count
* stability across symbols
* stability across time periods
* stability across regimes
* realistic fee sensitivity

Use:

* train/validation/test time splits
* walk-forward analysis
* parameter bounds
* out-of-sample evaluation
* minimum trade-count constraints

Prevent:

* future leakage
* configuration leakage
* repeated tuning on the final test set
* unrealistic leverage optimization
* selecting parameters based on one coin or one period

Persist calibration results and configuration IDs.

---

## Phase 11 — Paper trading integration

Integrate the finalized futures contracts and lifecycle with the existing paper-trading system.

Paper trading should:

* consume approved futures plans
* track waiting-for-entry setups
* detect fills
* reject missed entries
* invalidate broken setups
* apply partial targets
* update stops
* simulate fees and slippage
* track margin and wallet exposure
* model liquidation
* persist lifecycle events
* support restart/recovery
* produce performance reports

Do not bypass safety enforcement.

Add CLI commands for:

* recording generated plans
* updating market state
* reviewing open plans
* reviewing entered positions
* lifecycle history
* account summary
* realized and unrealized PnL

---

## Phase 12 — Testnet execution preparation

Only after deterministic backtests and paper trading are stable.

Testnet execution must remain isolated from live trading.

Requirements:

* explicit environment selection
* no live API endpoint by default
* isolated margin enforcement
* leverage-setting verification
* symbol precision handling
* minimum quantity/notional handling
* reduce-only exits
* client order IDs
* idempotent order submission
* retry handling
* reconciliation
* stale-order cancellation
* position-state recovery
* lifecycle persistence
* emergency shutdown
* daily-loss kill switch
* consecutive-loss kill switch
* maximum open-risk enforcement
* clear testnet warnings

Never silently fall back from testnet to live trading.

---

# Cross-cutting engineering requirements

## Determinism

Given identical:

* market data
* configuration
* account inputs
* timestamps

the system should produce identical analysis results.

Avoid hidden randomness.

## Configuration

Move tunable thresholds into validated configuration.

Do not scatter unexplained numeric constants across modules.

Configuration should include identifiers suitable for reproducibility.

## Domain boundaries

Maintain clean separation among:

* market data
* feature calculation
* structure/liquidity analysis
* scanner classification
* gainer classification
* strategies
* scoring
* risk
* futures account planning
* lifecycle
* backtesting
* paper trading
* execution

Avoid circular imports and giant modules.

## Compatibility

Preserve existing public APIs where practical.

When extending output, prefer additive fields.

Do not break existing CLI commands without a migration reason.

## Error handling

Return explicit reasons for:

* no trade
* rejected strategy
* rejected risk setup
* rejected futures account plan
* missed entry
* invalidated entry
* unsafe leverage
* excessive wallet exposure
* excessive loss
* liquidation danger
* stale or incomplete data

## Data quality

Expose and use:

* stale-data flags
* current-price source
* closed-candle timestamps
* missing optional-data flags
* provider errors
* spread/slippage confidence

Do not fabricate unavailable funding, open interest, order-book, or liquidation data.

## Type quality

* maintain strict typing
* avoid broad `Any` unless necessary at external boundaries
* use frozen dataclasses or frozen Pydantic models for domain contracts
* preserve timezone-aware datetimes
* use enums for finite states

## Documentation

Update:

* README
* CLI examples
* configuration documentation
* architecture notes
* phase completion notes

Document risk honestly.

Do not describe the system as guaranteed, impossible-profit, or loss-proof.

---

# Validation workflow

After each coherent phase:

1. Run formatting and lint checks.
2. Run strict type checking.
3. Run relevant unit tests.
4. Run the complete test suite.
5. Inspect CLI help.
6. Run deterministic fixture-based CLI examples.
7. Check that old commands still work.
8. Review generated JSON for stable schema.
9. Commit only coherent changes.

Expected commands should include the project's configured equivalents of:

```bash
ruff check .
ruff format --check .
mypy src
pytest
```

Use the exact commands defined by `pyproject.toml`.

When checks fail:

* identify the root cause
* fix the implementation
* do not weaken tests merely to make them pass
* do not disable type checking broadly
* do not add blanket ignores without justification

---

# Git workflow

The repository uses `main` directly.

Do not create unnecessary branches.

Before editing:

* inspect repository status
* inspect recent commits
* inspect `docs/modification.md`
* inspect current tests
* confirm the existing completed work listed in this prompt is present

During work:

* make small, coherent commits
* avoid overwriting unrelated changes
* do not delete working capabilities without a documented replacement
* keep commit messages clear and phase-specific
* push completed coherent changes to `main`

Do not stop after planning.

Implement the work.

---

# Progress tracking

Create or update a roadmap/progress file under `docs/`, for example:

* `docs/implementation_progress.md`

Track:

* completed phase
* files changed
* design decisions
* tests added
* checks run
* known limitations
* next phase

Update it after every completed phase.

Do not mark a phase complete unless its implementation and tests are present.

---

# Completion definition

The work is complete only when:

* all applicable requirements in `docs/modification.md` are implemented
* entry classification is precise and direction-aware
* leverage and margin geometry is account-aware and futures-correct
* normal and gainer scanners are separated
* gainer lifecycle exists
* strategies are regime-routed
* scalp and runner management works
* production pipeline can be backtested chronologically
* datasets and reproducibility metadata exist
* calibration is out-of-sample aware
* paper trading consumes the real futures-plan lifecycle
* testnet execution is safely isolated
* tests, lint, formatting, and typing pass
* CLI and README are updated
* no fake market data or fabricated signals are introduced

---

# Start now

Begin by:

1. Reading `docs/modification.md`.
2. Inspecting the current repository and recent futures-related commits.
3. Running the existing test suite before modifications.
4. Implementing the direction-aware entry-state classification engine.
5. Adding exhaustive boundary tests.
6. Integrating the result into futures-plan JSON, CLI text, and scanner output.
7. Running all checks.
8. Updating `docs/implementation_progress.md`.
9. Committing and pushing the completed entry-state phase.
10. Continuing sequentially through the remaining roadmap until the project reaches the completion definition.

Do not stop after the first phase unless there is a genuine external blocker.

When blocked by missing exchange data or credentials:

* complete provider-independent contracts and adapters
* add deterministic fixtures
* document the exact blocker
* continue all work that does not require those credentials

At the end, provide:

* completed phases
* files added or modified
* tests and checks run
* CLI examples
* remaining external blockers
* final architecture summary
* known risks and limitations

