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
- Approved futures plans serialize:
  - selected risk mode;
  - exact risk-mode configuration used;
  - account-policy configuration when supplied;
  - account-policy decision and drawdown state when supplied.
- Rejected plans return explicit mode-limit or account-policy lockout reasons.
- The legacy Phase-6 `RiskConfig` remains API-compatible but now resolves canonical limits
  from `config/futures.yaml` and `config/account_policies.yaml` when loaded.
- `config/risk.yaml` now owns only Phase-6 setup geometry and simulation inputs. Duplicate
  canonical account or futures fields are rejected with a validation error.
- A schema-versioned `AccountStateSnapshot` and atomic JSON `AccountStateStore` now persist:
  - trading day and start-of-day equity;
  - current balance and equity;
  - daily trade count;
  - consecutive losses;
  - total open risk;
  - directional and correlated exposure.
- Account-state transitions support validated entry registration, close registration,
  loss-streak updates, exposure release, and daily counter rollover.
- The active `paper record` CLI supports risk mode, account policy, persistent account state,
  wallet overrides, exposure overrides, session state, and weekend state.
- Policy lockouts are evaluated before a paper trade is recorded; rejected plans expose
  deterministic risk-mode or account-policy reasons.
- Account-policy evaluation checks projected exposure rather than existing exposure alone.
- Proposed exposure classification is deterministic and auditable:
  - every trade contributes its full modeled risk to its `LONG` or `SHORT` direction bucket;
  - stablecoin-quoted crypto pairs contribute full modeled risk to `CRYPTO_STABLE_QUOTE`;
  - crypto cross pairs use `CRYPTO_CROSS` without fabricated statistical correlation;
  - explicit CLI values override automatic exposure classification.
- Policy-aware paper plans preserve account-state registration metadata.
- Paper lifecycle updates synchronize entry, partial-close, terminal-close, exposure,
  balance, equity, and consecutive-loss state.
- Existing paper trades without account-state registration metadata remain readable.
- `.github/workflows/quality.yml` defines Ruff formatting, Ruff linting, strict mypy, and
  pytest checks for pushes to `main` and pull requests.
- The complete N1 local quality gate passed before commit `d45409c` was pushed to `main`.

### Known limitations

- Correlation classification is intentionally bucket-based and conservative; it is not a
  rolling statistical correlation matrix or portfolio beta model.
- Paper-trade and account-state files are each written atomically, but the two-file update is
  not a transactional database commit.
- Execution/testnet lifecycle events do not yet update persistent account state.
- `DEFAULT_RISK_CONFIG` remains a safe import-time fallback; production-style runs should
  use `load_risk_config()` so canonical mode and policy values are injected.

## N2 — Canonical Trade Management Plan

### Batch N2.1 implemented

- Added provider-independent `TradeManagementPlan` contracts in
  `src/apex/domain/trade_management.py`.
- Added canonical enums for current operator action, entry instruction, order type, stop
  type, and management trigger type.
- Added validated entry instructions with entry state, zone, ideal price, chase boundary,
  order recommendation, expiry field, and cancellation conditions.
- Added validated initial protection instructions containing stop, account risk, quantity,
  notional, margin, leverage, execution costs, liquidation estimate, and buffer.
- Added target-ladder legs with close percentage, cumulative percentage, expected R multiple,
  and rationale.
- Added stop-management and emergency-exit rule contracts.
- Added direction-aware validation for target ordering and exact 100% target allocation.
- Added deterministic entry-state-to-operator-action mapping.
- Added management-action-to-existing-lifecycle-event translation so N2 extends the current
  lifecycle rather than creating a second state machine.
- Exported all N2.1 contracts through `apex.domain`.
- Added focused tests for JSON serialization, allocation invariants, direction-aware target
  geometry, contradictory action rejection, deterministic entry mapping, and lifecycle replay.

### Batch N2.2 implemented

- Added application-layer `build_trade_management_plan()` composition without moving
  orchestration into domain models.
- Every policy-approved futures plan now serializes a complete `management_plan` alongside
  entry, precision-entry, stop, target, position, lifecycle, risk-mode, and account-policy data.
- Current operator action is derived deterministically from the canonical entry state.
- Entry instructions serialize an order recommendation and direction-aware cancellation rules
  for structural invalidation, maximum-chase breach, lifecycle invalidation, expiry, and account
  lockout.
- Initial protection is populated from the already validated futures position model rather than
  recalculating or fabricating risk, sizing, execution costs, leverage, or liquidation data.
- Target legs now include deterministic cumulative allocation and direction-aware expected
  R multiples calculated from the approved ideal entry and structural stop.
- The first completed target produces a canonical breakeven stop-movement instruction; the
  instruction explicitly forbids tightening before the target trigger.
- Emergency rules cover structural invalidation, configured spread-safety failure, and active
  account-policy lockout.
- Existing short-plan fixtures now use directionally valid short targets, allowing N2 target
  validation to catch genuine contradictions rather than preserving invalid test geometry.
- Added integration assertions for ready-now, missed-entry, short-retest, manual-leverage,
  protection, allocation, R-multiple, breakeven, and emergency-exit serialization.
- Exported `build_trade_management_plan()` through `apex.application`.

### N2 remaining work

- Add calibrated structural trailing and explicit runner rules without assuming a runner when
  the approved target allocation already totals 100%.
- Serialize management plans in human-readable CLI reports as well as JSON.
- Update paper-trade reports from lifecycle state to one unambiguous current action.
- Add emergency-close, stop-update, runner, expiry, cancellation, and complete replay coverage.
- Run and record the complete Ruff, strict-mypy, and pytest gate for the integrated N2 changes.

No external or forward-validation claim is made by this implementation.
