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
- The active `paper record` CLI now accepts compact account context through:
  - risk-mode selection;
  - account-policy selection;
  - persistent account-state file selection;
  - optional wallet-balance override;
  - optional proposed directional and correlated exposure overrides;
  - session and weekend state.
- CLI account context derives policy state from the validated JSON snapshot rather than
  duplicating every persistent account-state field as a separate command option.
- Policy lockouts are evaluated before a paper trade is recorded; rejected plans expose
  the deterministic risk-mode or account-policy reasons.
- Account-policy evaluation checks projected exposure rather than existing exposure alone:
  - current total open risk plus proposed risk;
  - current directional exposure plus proposed directional exposure;
  - current correlated exposure plus proposed correlated exposure.
- Serialized account-policy decisions include all three projected exposure totals.
- Proposed exposure classification is deterministic and auditable:
  - every trade contributes its full modeled risk to its `LONG` or `SHORT` direction bucket;
  - stablecoin-quoted crypto pairs contribute full modeled risk to the shared
    `CRYPTO_STABLE_QUOTE` correlation bucket;
  - crypto cross pairs use `CRYPTO_CROSS` and do not fabricate statistical correlation;
  - explicit CLI values override automatic directional or correlated contributions.
- Approved futures plans serialize the selected buckets, exposure values, and whether each
  value came from automatic classification or an override.
- Policy-aware paper plans preserve account-state registration metadata.
- `paper update --account-state-file` synchronizes persistent state when lifecycle changes
  occur:
  - an actual entry increments daily trade count and total open risk;
  - partial closes release the matching fraction of tracked exposure;
  - terminal closes release remaining exposure and apply realized P&L;
  - losing closes increment the consecutive-loss counter;
  - profitable and breakeven closes reset the consecutive-loss counter.
- Existing paper trades without account-state registration metadata remain readable and do
  not mutate an account-state file.
- Paper recording without an account-state file remains compatible; classification is still
  serialized, but account-policy exposure mutation is not attempted.
- `.github/workflows/quality.yml` now defines the canonical repository quality gate for pushes
  to `main` and pull requests:
  - Ruff formatting check;
  - Ruff lint check;
  - strict mypy;
  - pytest.

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
- duplicate canonical-field rejection;
- account-state persistence round trips;
- entry, close, loss-streak, exposure, and day-roll transitions;
- transition-time invariant validation;
- CLI account-context default behavior, state-derived policy resolution, and mismatch
  rejection;
- paper entry, partial-close, terminal-close, loss-streak, metadata-compatibility, and
  non-fabricated exposure transitions;
- projected directional and correlated exposure approval, rejection, serialization, and
  proposed-exposure geometry validation;
- automatic stable-quote classification, conservative cross-pair handling, override
  preservation, and override geometry validation.

### Configuration ownership

- `config/futures.yaml`: canonical futures risk modes, execution costs, leverage bounds,
  margin assumptions, and liquidation assumptions.
- `config/account_policies.yaml`: personal, paper, and funded account restrictions,
  including account-level exposure and lockout limits.
- `config/risk.yaml`: Phase-6 setup geometry and simulation inputs only, including minimum
  reward, stop-distance geometry, chase limits, structural buffers, and the legacy
  liquidation-distance multiplier used by setup pre-screening.
- `config/default.yaml`: general application, routing, provider, and timeframe settings.

### N1 acceptance status

- Substantive N1 behavior is implemented.
- The canonical automated quality gate is committed to the repository.
- N1 is not formally marked complete until one full gate run is observed passing on `main`.
- The current execution environment could not clone GitHub because DNS resolution for
  `github.com` was unavailable, and Ruff/mypy were not installed locally. No false passing
  claim is made.

### Known limitations / remaining N1 work

- Correlation classification is intentionally bucket-based and conservative; it is not a
  rolling statistical correlation matrix or portfolio beta model.
- Paper-trade and account-state files are each written atomically, but the two-file update is
  not a transactional database commit.
- Execution/testnet lifecycle events do not yet update persistent account state.
- `DEFAULT_RISK_CONFIG` remains a safe import-time fallback; production-style runs should
  use `load_risk_config()` so canonical mode and policy values are injected.
- Observe and repair the first complete GitHub Actions quality-gate run before declaring N1
  complete and starting N2.

No external or forward-validation claim is made by this implementation.
