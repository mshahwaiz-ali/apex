# Apex Implementation Progress

## Next-stage roadmap

Authoritative plan: `docs/APEX_NEXT_STAGE_MASTER_PLAN.md`.

This document records implemented behavior only. It does not claim statistical
profitability or production readiness.

## N1 — Risk Consolidation and Account Policy

### Implemented

- Exactly three risk modes remain: `STANDARD`, `AGGRESSIVE`, and `EXTREME`.
- `STANDARD` is the default futures risk mode.
- All modes permit leverage down to `1x`; no mode requires unnecessary minimum leverage.
- Canonical mode defaults are owned by `config/futures.yaml` and validated by
  `src/apex/config/futures.py`.
- Mode defaults include per-trade modeled account loss, preferred and maximum leverage,
  wallet exposure, total open risk, daily loss, and consecutive-loss limits.
- `FuturesAccountInput` defaults to `STANDARD`.
- Configurable account-policy presets are owned by `config/account_policies.yaml`.
- Account-policy contracts and deterministic evaluation support:
  - internal daily drawdown lockout;
  - buffered total drawdown lockout;
  - maximum trades per day;
  - maximum consecutive losses;
  - maximum risk per trade;
  - maximum total open risk;
  - maximum directional exposure;
  - maximum correlated exposure;
  - required stop-loss;
  - weekend restrictions;
  - optional session restrictions.
- Public futures-plan approval applies risk-mode limits independently from an optional
  account policy.
- Approved futures plans serialize selected risk mode, exact mode configuration, account policy,
  and policy decision snapshots.
- Rejected plans return explicit mode-limit or account-policy lockout reasons.
- A schema-versioned atomic account-state store persists balance, equity, drawdown, trade count,
  loss streak, open risk, and exposure.
- Paper lifecycle updates synchronize entry, partial-close, terminal-close, exposure, balance,
  equity, and consecutive-loss state.
- Proposed exposure classification remains deterministic and bucket-based without fabricated
  statistical correlation.
- `.github/workflows/quality.yml` defines Ruff formatting, Ruff linting, strict mypy, and pytest.
- The complete N1 local quality gate passed before commit `d45409c` was pushed to `main`.

### Known limitations

- Correlation classification is intentionally bucket-based and conservative; it is not a rolling
  statistical correlation matrix or portfolio beta model.
- Paper-trade and account-state files are individually atomic but not a transactional multi-file
  database commit.
- Execution/testnet lifecycle events do not yet update persistent account state.

## N2 — Canonical Trade Management Plan

### Batch N2.1 implemented

- Added provider-independent `TradeManagementPlan` contracts in
  `src/apex/domain/trade_management.py`.
- Added canonical current-action, entry-instruction, order-type, stop-type, and trigger enums.
- Added validated entry, initial protection, target ladder, stop-management, and emergency-exit
  contracts.
- Added direction-aware target ordering, exact target allocation, deterministic entry action
  mapping, and lifecycle-event translation.

### Batch N2.2 implemented

- Added `build_trade_management_plan()` in the application layer.
- Every approved futures plan now serializes a complete `management_plan`.
- Management plans derive exact entry action, order type, risk details, direction-aware R
  multiples, cumulative target allocation, TP1 breakeven instruction, cancellation conditions,
  and emergency rules.
- Existing short fixtures were corrected to use directionally valid targets.

### Batch N2.3 reporting implemented

- Added `format_trade_management_plan()` for deterministic human-readable instructions.
- `apex analyze` text output now prints the current action, entry method, entry zone, ideal and
  chase prices, stop, risk, quantity, notional, margin, leverage, target ladder, stop rules,
  emergency rules, and entry cancellation conditions.
- JSON behavior remains unchanged and continues to serialize the full management plan.

### Batch N2.4 paper guidance implemented

- Added immutable `PaperTradeGuidance` output with one canonical current action, instruction,
  active stop, next target, and completed target labels.
- Guidance is derived from existing `PaperTradeState` and the serialized management plan without
  creating or mutating a second lifecycle state machine.
- Waiting trades return `WAIT`; entered trades return `HOLD`; partial trades return `MOVE_STOP`;
  invalidated and cancelled setups return `CANCEL_SETUP`; expired setups return `DO_NOT_ENTER`;
  completed trades return `CLOSE_ALL`.
- Added a schema-versioned operational report for batches of stored paper trades.
- Added focused tests for waiting, entered, partial, invalidated, cancelled, expired, stopped,
  target-complete, next-target progression, stop movement, and timezone validation.

### Batch N2.5 paper CLI integration implemented

- The corrected paper-command overlay now owns `record`, `update`, `report`, and `replay-report`.
- Legacy paper report commands are removed before corrected commands are registered, preventing
  duplicate command implementations.
- `paper record` prints the initial canonical operator action after persistence.
- `paper update` prints state, current action, and instruction for each selected trade after replay.
- `paper report` emits performance plus a schema-versioned guidance report in text or JSON.
- `paper replay-report` attaches lifecycle-backed guidance to the canonical replay audit payload.
- Both report commands support optional deterministic JSON file output.
- Policy-aware account-state synchronization and canonical symbol handling remain unchanged.

### Batch N2.6 expiry and advanced lifecycle guidance implemented

- Approved public futures plans now derive a timezone-aware entry expiry from the setup decision
  timestamp using a deterministic 15-minute default validity window.
- Rejected entry instructions remain non-actionable and carry no expiry.
- The public paper update API now routes through an expiry-aware candle-by-candle advancement
  wrapper, preventing a candle at or after expiry from filling a stale waiting setup.
- Explicit expiry produces a canonical `EXPIRED` lifecycle event and terminal paper state.
- Paper guidance now exposes the exact entry deadline, replayed lifecycle reason, runner-active
  flag, trailing-stop price, active stop, next target, and completed targets.
- Replayed runner events produce runner-hold guidance; trailing-stop events produce `MOVE_STOP`
  guidance with an explicit never-loosen instruction.
- Emergency and momentum-failure terminal reasons produce explicit emergency-close verification.
- Guidance report schema advanced to version 2.
- Added focused unit coverage for explicit expiry and replayed runner/trailing-stop guidance.

### Batch N2.7 corrected paper CLI coverage implemented

- Added corrected-overlay command-registration coverage for `record`, `update`, `report`, and
  `replay-report`.
- Added empty-store JSON integration coverage for `paper report`, including performance and
  guidance schema version 2.
- Added empty-store JSON integration coverage for `paper replay-report`, including replay counts
  and attached guidance.
- Test fixtures use typed pytest `MonkeyPatch` and `Path` inputs for strict-mypy compatibility.

### N2 quality-gate repair

Observed locally after pulling commit `de022ea` on 2026-07-14:

- `ruff format .`: 4 files required formatting.
- `ruff check .`: 9 lint errors.
- `mypy src`: 48 errors, concentrated in
  `src/apex/paper_trading/guidance.py`, caused by broadly typed
  dictionary expansion into `PaperTradeGuidance`.
- `pytest`: 655 passed and 9 failed.
- All nine failures were in
  `tests/unit/paper_trading/test_guidance.py`; legacy
  `SimpleNamespace` fixtures lacked `lifecycle_events` while guidance
  unconditionally invoked canonical lifecycle replay.
- `tests/unit/test_paper_cli_overlay.py` contained only partial command
  registration scaffolding and lacked JSON coverage for `report` and
  `replay-report`.
- The repair was completed and the full local quality gate passed with 668 tests.

## N3 — Futures Standard-Mode Quality Pass

### Implemented

- Added canonical strategy approval configuration in `config/strategy_approval.yaml`.
- Added strict typed configuration contracts in `src/apex/config/strategy_approval.py`.
- Every registered futures strategy must define `STANDARD`, `AGGRESSIVE`, and `EXTREME`
  thresholds; incomplete or unknown configuration fails validation.
- Strategies are classified as `PREFERRED`, `CONTROLLED`, or `RESTRICTED`.
- Added deterministic setup eligibility states:
  `FUNDED_ELIGIBLE`, `PAPER_ONLY`, `EXPERIMENTAL_ONLY`, and `REJECTED`.
- Added stable machine-readable approval and rejection reason codes.
- Added strategy-specific score-versus-threshold explanations.
- `STANDARD` setups without validated historical evidence remain `PAPER_ONLY`.
- `AGGRESSIVE` setups remain `PAPER_ONLY`; `EXTREME` setups remain
  `EXPERIMENTAL_ONLY`.
- Added a candidate-level quality gate that preserves raw Phase 5 scoring while enforcing:
  - a controlled threshold adjustment for breakout retests;
  - stricter direct-breakout extension, volume, and target-space requirements;
  - stricter momentum extension, volume, and momentum-quality requirements;
  - rejection of provisional gainer evidence in `STANDARD` mode.
- Added an optional Phase 5 approval overlay that preserves deterministic rank order and legacy
  scoring behavior unless a futures risk mode and strategy approval configuration are supplied.
- Added `analyze_futures_phase5()` as the application-level N3 orchestration helper.
- Policy-aware futures plans now serialize `strategy_approval` and `eligibility` and return
  structured strategy rejection payloads.
- Added focused tests for threshold routing, funded/paper/experimental eligibility,
  breakout-retest treatment, direct-breakout restrictions, and provisional gainer rejection.

### Completed integration and validation

- Futures approval is integrated with typed historical and forward-paper evidence.
- Exact matching `STANDARD` setup segments may become `FUNDED_ELIGIBLE` only after both historical
  out-of-sample and forward-paper validation pass.
- `AGGRESSIVE` remains `PAPER_ONLY`; `EXTREME` remains `EXPERIMENTAL_ONLY`.
- Canonical setup-segment identity is centrally derived from the approved setup, account risk mode,
  scanner context, market regime, and deterministic score band.
- Arbitrary caller-authored segment mappings are no longer accepted by futures-plan approval.
- The complete local quality gate passed with 930 tests after canonical segment integration.

No historical profitability, execution readiness, funded-account readiness, or production
eligibility claim is made by N3.

## N4 — Reproducible Futures Evidence Campaigns

### Batch N4.1 dataset foundation

- Added immutable futures candle dataset manifests.
- Dataset identity includes symbol, timeframe, provider, extraction timestamp, coverage bounds,
  candle count, schema version, and deterministic SHA-256 content hash.
- Dataset construction rejects mixed symbols, mixed timeframes, mixed providers, active candles,
  duplicate timestamps, and non-chronological candles.
- JSON persistence uses atomic replacement and fully revalidates manifest-to-content consistency
  when loading.
- This foundation does not claim historical edge; empirical baseline campaigns remain the next
  stage.

### Batch N4.2 historical acquisition CLI

- Added provider-independent historical dataset acquisition using the canonical candle provider.
- Acquisition accepts up to 10,000 provider candles per dataset.
- The currently active candle is excluded before reproducibility validation.
- Empty symbols, empty timeframes, invalid limits, naive extraction timestamps, and provider
  responses without closed candles fail explicitly.
- Dataset identifiers may be supplied by the operator or generated deterministically from symbol,
  timeframe, and extraction timestamp.
- Added `apex dataset acquire` with explicit timeframe, candle limit, output file, and optional
  dataset identifier.
- The CLI writes atomically, reloads the completed file, and verifies manifest/content consistency
  before reporting success.
- Acquiring a dataset does not establish historical edge or trading eligibility.

## V2 Spot Portfolio Backtester and Baseline Campaign Pipeline

### Implemented in the current large batch

- Added a separate `src/apex/spot_backtesting/` package. It does not reuse futures margin,
  leverage, liquidation, short-direction, or wallet-exposure logic.
- Added immutable long-only spot contracts for cash, allocation, entries, targets, regimes,
  holding duration, trades, equity points, and portfolio metrics.
- Added chronological multi-symbol portfolio simulation with stable timestamp, symbol, and plan
  ordering.
- Added portfolio-wide available-cash, stablecoin-reserve, per-position allocation, total
  exposure, and concurrent-position constraints.
- Added deterministic transaction fees and adverse entry/exit slippage.
- Added bounded planned scale-ins, partial exits, target ladders, protective stops, setup expiry,
  time exits, broad-market regime exits, and final marking.
- Stops and regime exits are processed before targets on ambiguous existing-position candles;
  newly opened positions cannot claim a target on the same candle.
- Added expectancy-focused metrics: trade count, win rate, average return, expectancy, profit
  factor, maximum portfolio drawdown, ending equity, total return, exposure utilization,
  concurrent positions, holding duration, and strategy/symbol/regime/score/exit breakdowns.
- Added `src/apex/spot_baseline/` with deterministic frozen campaign planning across strategies,
  symbols, train/validation/test datasets, fee/slippage variants, and allocation variants.
- Frozen plans require all three dataset roles, complete symbol coverage, unique variants, stable
  dataset hashes, a stable assumptions hash, a complete campaign-cell matrix, and a deterministic
  plan ID.
- Added campaign execution that binds strategy-generated plans and bars to every frozen cell and
  rejects missing or extra inputs and strategy/symbol mismatches.
- Added completed-result validation for missing/duplicate cells, plan drift, assumptions drift,
  dataset drift, and cost/allocation mismatch.
- Strategy verdicts use only train and validation cells. Frozen final-test cells are executed,
  validated, and retained but cannot influence baseline selection.
- Added frozen reports with `ACCEPT`, `RESTRICT`, `REJECT`, and `INSUFFICIENT_EVIDENCE` verdicts,
  machine-readable reasons, portfolio expectancy/drawdown/return, coverage, score bands, cost
  sensitivity, exposure statistics, deterministic report IDs, and explicit research warnings.
- Added JSON and SQLite report persistence with deterministic upsert/load behavior.
- Added focused deterministic tests for long-only separation, allocation and exposure caps,
  insufficient cash, fees/slippage, bounded scale-ins, partial exits, regime exits, conservative
  same-candle ordering, drawdown/exposure metrics, campaign completeness/drift, deterministic IDs,
  JSON round-trip, and SQLite upsert/load.

### Explicitly remaining

- Full local Ruff, strict mypy, and pytest validation for this batch has not yet been reported.
- Live spot strategy generation, provider integration, and user-facing CLI commands remain.
- Sector/correlation exposure limits and higher-timeframe stop movement remain.
- Forward-paper spot validation and final-test attachment/reporting remain separate later gates.
- No funded, production, or real-money readiness is claimed.

## N4.3 — Deterministic chronological dataset splitting

### Implemented

- Added provider-independent contracts for chronological train, validation, and final-test
  dataset splits.
- Added configurable validated ratios with deterministic integer allocation and a minimum
  of one candle in every split.
- Child datasets preserve the exact parent candle ordering and use deterministic parent-derived
  identifiers ending in `-train`, `-validation`, and `-final-test`.
- Added a schema-versioned split-set manifest containing parent identity and hash, child identities
  and hashes, ratios, counts, and inclusive coverage boundaries.
- Added verification that child datasets do not overlap, duplicate, reorder, omit, or introduce
  candles and that their concatenation exactly reconstructs the loaded parent dataset.
- Added atomic split-manifest persistence and complete reload verification for all four written
  artifacts.
- Added `apex dataset split` with explicit input, child-output, manifest-output, and optional ratio
  flags.
- The CLI reloads and verifies the parent, three children, and split-set manifest before reporting
  `DATASET_SPLIT`.
- Added focused coverage for deterministic boundaries, odd counts, ratio validation, minimum
  sizes, reconstruction, overlap prevention, tampered hashes, JSON round trips, and CLI
  registration.

## N4.4 — Deterministic historical dataset campaign planning

### Implemented

- Added provider-independent contracts for reproducible multi-symbol historical dataset campaigns.
- Campaigns define a stable campaign ID, symbol universe, timeframe, provider, candle count, output
  directory, chronological split ratios, and deterministic acquisition order.
- Planning is intentionally candle-count based because the current provider abstraction does not
  expose historical start/end-period acquisition.
- Symbols are normalized, duplicate symbols are rejected, and jobs are sorted deterministically
  regardless of input ordering.
- Every job declares the expected parent dataset, train dataset, validation dataset, final-test
  dataset, and split-manifest identifiers and output paths.
- Parent IDs are deterministically derived from campaign ID, symbol, and timeframe; child IDs retain
  the canonical `-train`, `-validation`, and `-final-test` suffixes.
- Campaign construction rejects conflicting artifact paths and conflicts with the campaign manifest
  output path.
- Added schema-versioned atomic campaign-plan persistence with complete reload validation.
- Added `apex dataset campaign-plan` with symbols-file, timeframe, candle-count, provider,
  output-directory, split-ratio, and manifest-output options.
- Campaign planning remains separate from acquisition, splitting, signal generation, backtesting,
  calibration, and campaign execution.
- Added focused tests for deterministic ordering, stable IDs, duplicate symbols, invalid ratios,
  conflicting paths, JSON round trips, tamper detection, CLI registration, and CLI persistence.

## N4.5 — Deterministic historical dataset campaign execution

Implemented provider-independent, fail-fast execution of frozen N4.4 campaign
plans.

Capabilities:

- consumes a loaded and validated `FuturesDatasetCampaignPlan`
- validates the frozen provider against the configured provider
- rejects all pre-existing planned artifacts before acquisition starts
- executes jobs strictly in frozen acquisition order
- uses exact planned symbols, timeframes, candle counts, dataset IDs, split
  ratios, and artifact paths
- reloads and verifies every parent dataset
- reloads and verifies every complete chronological split set
- verifies generated child IDs against the frozen campaign plan
- removes artifacts created by the current attempt after a job failure
- never writes a completed execution manifest after partial failure
- persists schema-versioned completed execution manifests atomically
- reloads and validates completed execution manifests
- exposes `apex dataset campaign-execute`

N4.5 remains limited to historical dataset acquisition and splitting. It does
not perform feature generation, signal generation, strategy replay,
backtesting, calibration, paper trading, or execution.

