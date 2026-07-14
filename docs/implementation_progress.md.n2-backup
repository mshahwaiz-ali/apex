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

### N2 remaining work

- Run and observe the complete Ruff format, Ruff lint, strict mypy, and pytest gate for all N2
  batches.
- Repair any quality-gate findings before declaring N2 complete.
- Add deeper mocked execution-path coverage for network-dependent `paper record` and `paper update`
  only if the quality gate exposes gaps in those paths.

The attempted local gate run on 2026-07-14 did not execute because the isolated runner could not
resolve `github.com` to clone the repository. No passing or failing quality result is claimed.

No external or forward-validation claim is made by this implementation.