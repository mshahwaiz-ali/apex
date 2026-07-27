# Apex Precision-First Implementation Report

**Implementation date:** 2026-07-27  
**Runtime default:** `observe_only`  
**Production promotion:** not approved

## Outcome

The precision-first prediction and abstention infrastructure is implemented
without loosening any deterministic trade rule. Apex can now freeze
decision-time candidate features, keep future outcomes separate, train the two
required model families, evaluate payoff-aware precision frontiers, record
runtime pass/abstain/unavailable decisions, and persist the evidence across
scan, analyze, backtest, JSON, and SQLite.

No model or threshold was promoted. Existing empirical evidence remains below
the locked profitability gates, and the required fresh post-June-2026 and
eight-week paper populations do not yet exist.

## Added

### Point-in-time research contracts

`src/apex/research/precision.py` adds:

- `CandidateFeatureSnapshot`;
- `CandidateOutcomeLabel`;
- deterministic feature and geometry identities;
- missing-value masks;
- canonical/shadow population labels;
- geometry deduplication;
- separate fill and post-fill training rows;
- atomic JSONL feature-row export;
- precision-frontier and validation-only threshold selection;
- historical and paper promotion evaluators.

The feature builder has no future-candle or outcome argument. Changing a later
target/stop result cannot change the frozen feature ID.

### Group-safe training

`src/apex/research/splits.py` now permits multiple candidates at one decision
timestamp while keeping their group in one partition. Purge and embargo operate
on unique decision times and are expanded back to candidate rows.

`src/apex/research/training.py` continues to compare fixed-seed logistic
regression and histogram gradient boosting, calibrates on validation only, and
selects a precision threshold from the validation frontier. The untouched
final partition is evaluated only after selection.

### Runtime precision gate

`src/apex/application/runtime_precision.py` adds:

- `RuntimePrecisionArtifact`;
- `RuntimePrecisionProfile`;
- `RuntimePrecisionDecision`;
- `pass`, `abstain`, and `unavailable` states;
- checksum and schema validation;
- calibrated fill and positive-net probabilities;
- expected-R point and interval evidence;
- segment sample authority and reason codes;
- observe-only, paper, and enforce behavior.

The gate runs after methodology, HTF, geometry, and deterministic selection.
Observe-only and paper modes do not mutate selection. Enforce mode is
fail-closed and requires both historical and paper promotion flags from a
trusted checksum-verified artifact.

### Payoff shadows

`src/apex/research/payoff.py` adds isolated comparisons for:

- canonical execution;
- confirmation/retest entry;
- no-chase;
- TP1 full exit;
- TP1 partial plus breakeven/runner;
- higher-cost stress;
- delayed-fill stress.

Every result is `shadow_only`; no stop is moved and no target is invented. The
tested configurations are countable for DSR/PBO.

### Runtime and persistence integration

The shared discovery pipeline now emits:

- additive `precision_gate` metadata;
- canonical and counterfactual `candidate_feature_snapshots`;
- stable feature identities across the shared scan/analyze/replay path.

Backtest schema v6 additionally emits separate
`candidate_outcome_labels`. SQLite schema v5 adds precision state,
positive-net probability, expected R, reasons, and artifact version without
removing older columns.

### Configuration and CLI

`config/default.yaml` adds:

- mode;
- trusted artifact path;
- minimum positive-net probability;
- minimum expected-R lower bound;
- minimum segment support;
- fail-closed enforcement behavior.

`apex research campaign` adds paired feature-snapshot and candidate-outcome
JSONL options. Existing public command names are unchanged.

## Updated

- `README.md` explains precision authority, default observe-only behavior, and
  the fact that higher displayed accuracy is not enough without positive
  expectancy.
- `commands.md` documents feature/outcome export and model-training usage.
- `docs/apex_quality_recovery_validation_report.md` records the implementation,
  promotion lock, tests, and archive smoke.
- `docs/apex_calibration_campaign_report.md` preserves the actual historical
  result and explains why it was not promoted.
- scan/analyze/backtest serialization and operator output show abstention
  reasons without presenting rule scores as probabilities.

## Deleted

Nothing was deleted for this precision-first patch. Existing uncommitted work
was preserved, no report was hidden, and no Git history was rewritten.

## Why production remains unchanged

The best prior validation-only accuracy lane was `72.8395%`, but expectancy was
`-0.053628 R` and profit factor was `0.819094`; its average loss exceeded its
average win by more than three times. The best clean untouched selected rule
was `50.9259%` with `-0.384038 R` expectancy and `0.547803` profit factor.

Those results fail the locked gates. Enforcement also requires at least 200
fresh untouched filled outcomes and then at least 50 resolved paper fills over
eight weeks with symbol/cohort diversity. Consequently the correct current
state is observe-only, not a manufactured 85–90% claim.

## Verification

- all 1,930 tests passed;
- Ruff passed across source, tests, and tools;
- mypy passed across all 331 authoritative source files;
- `apex config-check --output json` passed;
- research CLI exposes both feature/outcome options;
- SQLite additive precision persistence passed;
- `git diff --check` passed;
- no retired methodology authority trace exists in the current tracked tree.

A real three-decision BTCUSDT archive smoke produced:

- schema v6 plus the v5 compatibility marker;
- 18 decision-time feature snapshots;
- 10 separate resolved outcome labels;
- zero production trades.

## Next evidence gate

Freeze a candidate model before consuming complete post-June-2026 data. If the
historical gates pass, switch only to paper mode. Enforcement may be enabled
only after every eight-week paper gate also passes. No trade-frequency quota
may override this sequence.
