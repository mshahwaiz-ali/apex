# S1 — Spot Domain and Configuration Foundation

## Status

Implementation is present on `main`. The complete local quality gate remains pending.

This document records implemented contracts and boundaries only. It does not claim that
spot strategy selection, market-regime analysis, sizing orchestration, backtesting, paper
trading, or production readiness are complete.

## Subphase plan

### S1.1 — Product boundary

- Introduce spot-specific direction, order-side, decision, entry-state, regime, and lifecycle
  semantics.
- Keep all contracts provider-independent and separate from perpetual-futures models.
- Make the initial product long-only and unleveraged.

### S1.2 — Account and planning contracts

- Add quote-balance and asset-balance inputs.
- Add fixed one-to-three-leg entry plans.
- Add structural invalidation and protective-stop plans.
- Add ordered scale-out targets.
- Add cash-funded position plans and lifecycle snapshots.

### S1.3 — Typed configuration

- Add a dedicated `config/spot.yaml` source of truth.
- Validate allocation limits, stablecoin reserve, entry allocation, target allocation, holding
  horizon, and timeframe policy.
- Reject leverage, borrowing, and lower-timeframe thesis configuration.

### S1.4 — Application boundary and public APIs

- Add a spot account-input resolver.
- Export spot contracts through the domain, configuration, and application public APIs.
- Preserve all futures exports and behavior unchanged.

### S1.5 — Focused validation

- Cover deterministic serialization and account invariants.
- Cover planned scale-in and scale-out geometry.
- Cover stop, sizing, and lifecycle invariants.
- Prove spot payloads contain no futures-only leverage, margin, or liquidation fields.

## Implemented contracts

`src/apex/domain/spot.py` now owns:

- `SpotDirection`
- `SpotOrderSide`
- `SpotDecision`
- `SpotMarketRegime`
- `SpotEntryState`
- `SpotLifecycleState`
- `SpotBalanceInput`
- `SpotAccountInput`
- `SpotEntryLeg`
- `SpotEntryPlan`
- `SpotStopPlan`
- `SpotTargetLeg`
- `SpotTargetPlan`
- `SpotPositionPlan`
- `SpotLifecycleSnapshot`

All models are frozen Pydantic v2 contracts with `extra="forbid"` and deterministic JSON
serialization.

## Explicit spot-versus-futures separation

The S1 spot contracts do not model or accept:

- leverage selection;
- isolated or cross margin;
- required margin;
- liquidation price;
- maintenance margin;
- stop-to-liquidation buffers;
- borrowed assets;
- perpetual-futures execution semantics.

Spot positions are cash-funded from available quote balance. `BUY` opens or increases the
initial long-only spot position; `SELL` reduces or closes owned inventory. Margin trading is
outside S1.

## Configuration defaults

`config/spot.yaml` defines:

- primary thesis timeframes: `1w`, `1d`, `12h`, and `4h`;
- optional execution refinement: `1h`;
- forbidden thesis timeframes: `1m`, `3m`, and `5m`;
- maximum allocation per position;
- maximum total spot exposure;
- maximum correlated-sector exposure;
- minimum quote-asset reserve;
- maximum simultaneous positions;
- maximum modeled account loss;
- fixed entry-leg and target-leg allocation defaults;
- maximum intended holding period and review interval.

The defaults are planning baselines, not calibrated production thresholds.

## Validation boundary

Focused tests were added under:

- `tests/unit/domain/test_spot.py`
- `tests/unit/config/test_spot.py`
- `tests/unit/application/test_spot_account.py`

The full repository quality gate has not been run in the GitHub connector environment. S1
must not be declared quality-gate complete until the local commands below pass:

```bash
ruff format .
ruff check .
mypy src
pytest
```

Any findings from that gate must be repaired before S1 is finalized.

## Deferred to later spot phases

S1 intentionally does not implement:

- broad-market regime calculation;
- spot symbol eligibility scanning;
- spot strategy generation or approval;
- risk-based versus allocation-capped sizing orchestration;
- live market-data integration for spot timeframes;
- spot analysis output orchestration;
- spot backtesting or paper-trade persistence;
- exchange order execution.
