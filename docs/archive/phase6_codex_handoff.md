# Phase 6 Codex Handoff

`docs/plan.md` remains the authoritative roadmap. This document summarizes the current Phase 6 implementation state.

## Phase 6 Scope

Phase 6 implements deterministic risk analysis after Phase 5 selection. It consumes `Phase5AnalysisResult`, evaluates only `selected_candidate`, and returns either an approved risk setup or explicit rejection codes.

Implemented responsibilities:

* actionable entry zone with maximum chase boundary
* structural stop using the Phase 4 invalidation concept plus configurable buffer
* target reward and risk-to-reward calculation
* account-risk-based position sizing
* required leverage, modeled maximum leverage, and liquidation buffer checks
* aggregate, same-direction, correlated, concurrent, daily-loss, and consecutive-loss exposure controls
* validated YAML risk configuration loading

Out of scope for Phase 6:

* CLI, scanner, reporting, backtesting, paper trading, order placement, execution, and trade management
* rescoring or reranking Phase 5 candidates
* rerunning candle, feature, structure, liquidity, or strategy analysis

## Files Implemented

* `src/apex/risk/config.py`
* `src/apex/risk/contracts.py`
* `src/apex/risk/engine.py`
* `src/apex/risk/__init__.py`
* `config/risk.yaml`
* `tests/unit/risk/test_phase6_engine.py`
* `tests/architecture/test_phase6_boundaries.py`
* `docs/phase6_codex_handoff.md`

## Public APIs

Exports from `apex.risk`:

* `RiskConfig`
* `RiskProfile`
* `ExposureState`
* `DEFAULT_RISK_CONFIG`
* `load_risk_config`
* `ActionableEntry`
* `StopLoss`
* `TakeProfit`
* `PositionSize`
* `LeverageRange`
* `RiskApprovedSetup`
* `RiskAssessment`
* `RiskDecision`
* `RiskRejectionCode`
* `analyze_phase6`

Primary entry point:

```python
from apex.risk import ExposureState, load_risk_config, analyze_phase6

config = load_risk_config("config/risk.yaml")
assessment = analyze_phase6(phase5_result, config=config, exposure=ExposureState())
```

## Risk Invariants

Contracts are frozen dataclasses. Phase 6 enforces:

* all public numeric outputs are finite and positive where applicable
* approved confidence is between 0 and 100
* entry lower bound cannot exceed upper bound
* preferred entry must lie inside the entry zone
* current-price-inside-zone flag must match entry bounds
* long maximum chase price cannot be below the entry zone
* short maximum chase price cannot be above the entry zone
* long stops are below the entry zone; short stops are above it
* long targets are above the entry zone; short targets are below it
* required leverage cannot exceed approved leverage maximum
* liquidation remains beyond the structural stop
* duplicate rejection codes are rejected
* approved assessments cannot contain rejection reasons
* rejected assessments require aligned rejection codes and reasons

## Rejection Behavior

`analyze_phase6` returns `RiskDecision.REJECTED` with explicit codes for:

* no selected Phase 5 candidate
* extended entry or current price beyond chase boundary
* stop too tight
* stop too wide
* insufficient target space
* unsafe leverage
* maximum concurrent trades
* maximum open risk
* maximum same-direction risk
* maximum correlated risk
* daily realized-loss limit
* consecutive-loss limit

Exposure rejections are aggregated so all applicable exposure-limit failures are visible in one assessment.

## Configuration Fields

`config/risk.yaml` currently maps to `RiskConfig`:

* `profile`
* `account_equity`
* `risk_per_trade_pct`
* `minimum_risk_reward`
* `minimum_stop_distance_pct`
* `maximum_stop_distance_pct`
* `structural_stop_buffer_pct`
* `maximum_entry_chase_pct`
* `maximum_leverage`
* `maintenance_margin_pct`
* `liquidation_buffer_ratio`
* `maximum_concurrent_trades`
* `maximum_open_risk_pct`
* `maximum_directional_risk_pct`
* `maximum_correlated_risk_pct`
* `maximum_daily_loss_pct`
* `maximum_consecutive_losses`

Unknown YAML fields are rejected.

## Test Coverage

Covered by `tests/unit/risk/test_phase6_engine.py`:

* approved long setup
* approved short setup
* Phase 5 no-trade propagation
* selected-candidate-only consumption
* explicit extended-entry rejection
* long and short chase-boundary rejection
* stop tight/wide rejection
* target-space rejection
* position sizing risk invariant
* unsafe leverage rejection
* exposure-limit rejection aggregation
* config non-finite value validation
* invalid exposure state validation
* approved setup entry-flag and chase-boundary invariants
* frozen risk contracts
* checked-in YAML loading and unknown-field rejection

Covered by `tests/architecture/test_phase6_boundaries.py`:

* future-phase terms are absent from the risk package
* future-phase packages are not imported by the risk package

## Quality-Gate Results

Last local non-git gate:

```text
.venv/bin/python -m ruff check .
All checks passed!

.venv/bin/python -m ruff format --check .
131 files already formatted

.venv/bin/python -m mypy src
Success: no issues found in 75 source files

.venv/bin/python -m pytest --cov=apex --cov-report=term-missing
331 passed
TOTAL coverage: 87%
```

Git operations were intentionally not run during this handoff pass. Run this before committing:

```text
git diff --check
```

## Remaining Limitations

* Exposure state is caller supplied; Phase 6 does not own portfolio state or persistence.
* Correlation grouping is represented as supplied correlated exposure amount, not computed from symbols.
* Position sizing does not model exchange precision, fees, or slippage.
* Target selection uses strategy-provided target concepts and does not invent new targets.
* Phase 6 does not run full validation gates automatically.
