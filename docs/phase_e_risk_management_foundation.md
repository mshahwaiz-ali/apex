# Phase E Risk And Trade Management Foundation

This note records the first Phase E hardening slice.

## Added

- Stop-loss outputs now include:
  - `quality_score`
  - `quality_band`
- Take-profit outputs now include deterministic `partial_close_pct`.
- Approved setups now include management policies for:
  - breakeven behavior
  - trailing behavior
  - time-based stale setup handling
  - momentum-failure reduction or exit

## Derivation

- Stop quality blends stop-distance placement, structure quality, and entry
  quality into a bounded `0.0..1.0` score.
- Target partials are deterministic:
  - one target: 100%
  - two targets: 50% / 50%
  - three or more targets: 40% / 35% / evenly split runner remainder

## Compatibility

- Existing exposure controls, leverage safety, rejection codes, and risk sizing
  remain unchanged.
- Existing `StopLoss` and `TakeProfit` constructors remain compatible through
  default values.
