# Apex Quality Recovery Audit

**Authority version:** `quality-recovery-v1`  
**Status:** implemented-behavior and evidence authority  
**Last repository audit:** 2026-07-27

This document describes the current Apex methodology. It is not a promise of
profitability and it is not a backlog. Future work belongs in
`docs/apex_quality_recovery_plan.md`.

## Canonical decision chain

```text
CLI scan/analyze/backtest
  -> application canonical_scan/selected_symbol
  -> decision_analysis
  -> integrated_analysis
  -> discovery_analysis
  -> shared StrategyContext and CanonicalMarketSnapshot
  -> strategy candidates
  -> hierarchical timeframe routing
  -> methodology and geometry enforcement
  -> canonical candidate selection
  -> opportunity portfolio
  -> text/JSON and chronological replay
```

`scan` and `analyze` share the selected-symbol authority. Historical replay calls
that same authority through a provider that exposes only information available
at each decision time. Public command names remain `scan`, `analyze`, `backtest`,
`research campaign`, `config-check`, and `version`.

## Implemented invariants

- Closed market data is the analytical authority; active candles are provisional.
- Market structure supplies direction and targets. Indicators, volume,
  derivatives evidence, and candlesticks are supporting evidence.
- Candlesticks cannot independently create direction or targets.
- Long and short candidates share the same snapshot, regime, geometry, costs,
  and deterministic arbitration.
- Fatal validity and geometry defects cannot be repaired by a high rank score.
- Setup validity is separate from execution availability and conditional
  activation.
- Missing optional evidence stays unavailable rather than becoming zero.
- Canonical, conditional, opportunity, and shadow replay populations remain
  separate.
- A 0-100 quality score is a rule/rank score, not a win probability.

## Current contracts and lineage

| Area | Authority | Current behavior |
|---|---|---|
| Market context | `discovery_context.py` | Builds role-aware closed-candle frames and explicit data quality |
| Snapshot | `quality_contracts.py` | Adds immutable point-in-time lineage, evidence availability, precision, staleness, and costs |
| Strategy production | `strategies/analysis.py` and registry | Produces specialized candidates against one context |
| Timeframe authority | `hierarchical_timeframe_routing.py` | Prevents execution frames from replacing higher-timeframe structure |
| Geometry | methodology geometry modules | Validates entry, invalidation, cost room, targets, and chase |
| Portfolio | `opportunity_portfolio.py` | Separates executable, conditional, developing, missed, and invalid states |
| Replay | `historical_signal_replay.py` and backtesting engine | Freezes closed prefixes and applies conservative lifecycle simulation |
| Configuration | Pydantic settings and `configuration_identity.py` | Validates YAML, hashes the resolved snapshot, and exposes parameter provenance |

## Source roles

- John J. Murphy: trend and swing structure, support/resistance, confirmation,
  role reversal, channels, and structural objectives.
- Steve Nison: completed-candle context, confirmation, timing, invalidation, and
  confluence. Candle evidence is never an independent target engine.
- Mark Douglas: probabilistic wording, predefined risk, immutable rules during an
  experiment, and evaluation over samples rather than one outcome.

The local Murphy scan ends during the head-and-shoulders discussion. Apex must
not attribute uncovered later-book material to that file.

## Confirmed limitations

- Historical candle replay cannot reconstruct unavailable derivatives evidence;
  candle-only decisions are explicitly degraded.
- Actual historical funding is downloaded by research campaigns but is not yet
  applied event-by-event by single-symbol replay.
- Behavior cohorts and snapshot metadata are observe-only; they do not authorize
  trades.
- PBO is unavailable until fold-level results from multiple tried
  configurations exist.
- Calibration remains non-authoritative until untouched, cost-aware outcomes are
  sufficiently populated.

## Evidence gates

Production changes require prefix-invariant feature calculation, chronological
replay, an untouched final test, conservative costs, canonical/shadow separation,
and stable behavior across folds, symbols, cohorts, and nearby parameters. Zero
trades is a valid result.
