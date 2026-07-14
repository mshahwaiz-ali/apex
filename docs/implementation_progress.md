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

### Tests added or updated

- canonical three-mode configuration;
- `STANDARD` defaults;
- `1x` leverage compatibility;
- invalid leverage ordering;
- invalid account-policy drawdown geometry;
- daily and total drawdown lockouts;
- trade-count and consecutive-loss lockouts;
- open-risk and required-stop enforcement;
- policy-aware futures approval;
- serialized risk and policy snapshots;
- oversized account-loss override rejection;
- compatibility updates for futures-plan tests;
- canonical Phase-6 risk configuration resolution;
- aggressive profile mapping;
- duplicate canonical-field rejection.

### Configuration ownership

- `config/futures.yaml`: canonical futures risk modes, execution costs, leverage bounds,
  margin assumptions, and liquidation assumptions.
- `config/account_policies.yaml`: personal, paper, and funded account restrictions,
  including account-level exposure and lockout limits.
- `config/risk.yaml`: Phase-6 setup geometry and simulation inputs only, including minimum
  reward, stop-distance geometry, chase limits, structural buffers, and the legacy
  liquidation-distance multiplier used by setup pre-screening.
- `config/default.yaml`: general application, routing, provider, and timeframe settings.

### Known limitations / remaining N1 work

- CLI inputs do not yet expose account-policy selection or live account-policy state.
- Persistent daily counters and account lockout state are not yet stored by a dedicated
  account-state service.
- Proposed directional and correlated exposure are not yet modeled separately from
  currently open exposure.
- `DEFAULT_RISK_CONFIG` remains a safe import-time fallback; production-style runs should
  use `load_risk_config()` so canonical mode and policy values are injected.
- The complete local quality gate is intentionally deferred until the end of the current
  implementation sequence or until a high-risk compatibility change requires it.

No external or forward-validation claim is made by this implementation.
