# N3 Strategy Approval Foundation

## Status

N3.1 is implemented on `main` as a configuration and typed-contract foundation.
The complete local Ruff, mypy, and pytest gates have not yet been observed for
this batch and must be run before N3.1 is declared quality-gate complete.

## Canonical configuration

`config/strategy_approval.yaml` owns the initial strategy-specific minimum
scores for each canonical `StrategyType` and each supported futures `RiskMode`.

The configuration deliberately covers only strategy identifiers that currently
exist in the domain:

- `trend_pullback`
- `breakout_continuation`
- `liquidity_reversal`
- `range_reversal`
- `momentum_continuation`
- `momentum_gainer_continuation`

A distinct breakout-retest strategy must be introduced in a later N3 batch only
when its strategy contract, generator, routing, evidence, and tests are added
together. N3.1 does not fabricate an unavailable strategy identifier.

## Validation guarantees

`StrategyApprovalConfig` and `StrategyApprovalRule` enforce:

- complete coverage of every canonical strategy;
- complete coverage of `STANDARD`, `AGGRESSIVE`, and `EXTREME`;
- score values between 0 and 100;
- rejection of unknown fields and unsupported enum values;
- deterministic threshold lookup by strategy and risk mode;
- explicit quality classes: `PREFERRED`, `CONTROLLED`, and `RESTRICTED`.

No global threshold fallback is provided. Missing or contradictory approval
configuration must fail validation rather than silently selecting another
value.

## Initial policy intent

- `trend_pullback` and `liquidity_reversal` are preferred controlled families.
- `range_reversal` is controlled and requires stronger approval.
- direct breakout, momentum continuation, and raw gainer continuation are
  restricted, especially in `STANDARD` mode.
- `AGGRESSIVE` and `EXTREME` remain available through explicit lower thresholds;
  neither mode bypasses configuration validation.

The values are planning defaults for deterministic routing. They are not
profitability claims and must later be calibrated through chronological,
out-of-sample, and forward-paper evidence.

## Next N3 batch

N3.2 should integrate this configuration into candidate approval and return
structured approval or rejection evidence containing:

- strategy;
- risk mode;
- observed score;
- required strategy threshold;
- quality class;
- stable reason code;
- deterministic human-readable explanation.

Existing risk, liquidation, account-policy, management-plan, and lifecycle
validation must remain authoritative and must not be weakened by strategy
approval routing.
