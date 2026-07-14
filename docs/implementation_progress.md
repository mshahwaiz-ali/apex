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
- Mode defaults now include per-trade modeled account loss, preferred and maximum
  leverage, wallet exposure, total open risk, daily loss, and consecutive-loss limits.
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
- Public futures-plan approval now applies risk-mode limits independently from an
  optional account policy.
- Approved futures plans serialize:
  - selected risk mode;
  - exact risk-mode configuration used;
  - account-policy configuration when supplied;
  - account-policy decision and drawdown state when supplied.
- Rejected plans return explicit mode-limit or account-policy lockout reasons.

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
- compatibility updates for futures-plan tests.

### Configuration ownership

- `config/futures.yaml`: futures execution costs, margin/liquidation assumptions,
  and canonical futures risk-mode defaults.
- `config/account_policies.yaml`: personal, paper, and funded account restrictions.
- `config/risk.yaml`: legacy Phase-6 setup-quality and exposure-engine configuration.
  It still contains overlapping account and futures fields and is not yet the final
  source of truth for those values.
- `config/default.yaml`: general application, routing, provider, and timeframe settings.

### Known limitations / remaining N1 work

- The legacy Phase-6 `RiskConfig` still owns several duplicated fields in
  `config/risk.yaml`. Removing them requires a focused compatibility migration because
  the existing setup risk engine consumes that contract directly.
- CLI inputs do not yet expose account-policy selection or live account-policy state.
- Persistent daily counters and account lockout state are not yet stored by a dedicated
  account-state service.
- Proposed directional and correlated exposure are not yet modeled separately from
  currently open exposure.
- The complete local quality gate must be run in a checkout with the project `.venv`:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy src
.venv/bin/python -m pytest
git diff --check
```

No external or forward-validation claim is made by this implementation.
