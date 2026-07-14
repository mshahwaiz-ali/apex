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

### N2 remaining work

- Integrate paper guidance into the active paper CLI/report commands.
- Add emergency-close, runner, and trailing guidance when those lifecycle events are generated.
- Add explicit entry expiry timestamps and cancellation execution.
- Run and observe the complete Ruff, mypy, and pytest gate for the N2 batches.

No external or forward-validation claim is made by this implementation.
