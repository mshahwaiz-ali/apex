# Apex Historical Learning and Strategy Discovery Plan

## Status

Approved future roadmap extension for the Apex next-stage master plan.

This document records the intended progression from deterministic historical replay to
controlled strategy improvement and later evidence-driven strategy discovery. It does not
claim autonomous intelligence, profitability, funded-account readiness, or production
readiness.

## Objective

Apex should learn from already-completed historical candles without waiting for future live
candles to develop.

At every historical decision timestamp, Apex must use only information that would have been
available at that exact timestamp. It may then inspect later candles solely to calculate the
outcome of the frozen decision.

The resulting historical experience should allow Apex to:

- measure how existing strategies actually behaved;
- compare successful and failed setup structures;
- improve deterministic thresholds and routing rules;
- identify recurring indicator, price-action, volume, and regime combinations;
- propose new candidate strategy families;
- reject unstable or overfitted discoveries;
- promote only strategies that survive out-of-sample and forward-paper validation.

## Core principle

Historical replay is accelerated experience, not permission to use future data.

For a decision timestamp `T`:

1. build the complete multi-timeframe snapshot using candles closed at or before `T`;
2. freeze the strategy decision, entry state, score, risk assumptions, and source data;
3. inspect candles after `T` only inside the outcome-labeling stage;
4. record favorable movement, adverse movement, targets, stop behavior, duration, and failure mode;
5. never feed those future outcomes back into the decision that was made at `T`.

## Required progression

### N4.7 — Historical signal-generation campaign

Consume the verified N4.6 dataset campaign and produce deterministic historical analysis
records.

Required behavior:

- load and verify the dataset campaign execution manifest;
- bind every record to exact dataset IDs, hashes, symbol, timeframe, and split role;
- construct chronological multi-timeframe snapshots without lookahead;
- run the existing analysis, routing, entry-state, scoring, and rejection pipeline;
- persist accepted and rejected candidates;
- preserve train, validation, and final-test separation;
- record strategy, direction, regime, score band, entry state, risk mode, and rejection reasons.

N4.7 generates decisions only. It does not determine whether a strategy is profitable.

### N4.8 — Historical outcome labeling and chronological replay

For every frozen historical decision, calculate what happened afterward.

Suggested outcome fields:

- maximum favorable excursion;
- maximum adverse excursion;
- TP1, TP2, runner, and stop outcomes;
- time to target;
- time to invalidation;
- breakout success or failure;
- reclaim or retest success;
- best and worst movement before resolution;
- fees and slippage-adjusted result;
- lifecycle exit reason;
- missed-entry and chase behavior;
- liquidation-buffer violations where applicable.

This stage must preserve conservative same-candle ordering and all existing lifecycle rules.

### N4.9 — Historical experience and feature dataset

Create a research dataset linking each frozen decision to its later outcome.

Features may include:

- candle body, wick, range, and close-location structure;
- volume and relative-volume behavior;
- RSI level, slope, reset, and reclaim behavior;
- MACD direction, acceleration, and cross state;
- EMA and VWAP distance;
- pullback depth;
- breakout extension;
- retest quality;
- volatility and liquidity regime;
- higher-timeframe alignment;
- market regime;
- gainer state;
- time since expansion;
- score components and rejection reasons.

Unavailable inputs must remain explicitly missing. Apex must never fabricate order flow, open
interest, funding, liquidation, or taker-flow data.

### N4.10 — Controlled strategy calibration

Use train data to improve existing deterministic strategies.

Allowed changes:

- threshold adjustment;
- score-weight adjustment;
- strategy-routing refinement;
- regime-specific activation or rejection;
- entry-zone, chase, reclaim, and retest limits;
- stop and target geometry calibration;
- lifecycle timing and momentum-failure thresholds.

Every calibrated configuration must be versioned, reproducible, and evaluated on untouched
validation data.

Final-test data must not influence calibration.

### N4.11 — Pattern discovery and candidate strategy proposals

Apex may search historical experience for recurring combinations that are not fully represented
by the existing strategy library.

Candidate examples may include:

- fast-gainer micro reclaim;
- shallow first-pullback continuation;
- high-relative-volume breakout retest;
- failed breakout with momentum divergence;
- volatility-compression squeeze continuation;
- sweep, reclaim, and acceleration sequences.

A discovered pattern is only a candidate hypothesis. It must be translated into an explicit,
deterministic, human-readable rule set containing:

- activation conditions;
- required evidence;
- entry geometry;
- maximum chase;
- invalidation;
- targets;
- management rules;
- applicable regimes;
- known failure conditions;
- minimum evidence requirements.

Black-box discoveries that cannot be explained or replayed deterministically must not be promoted.

### N4.12 — Walk-forward validation and strategy promotion

Each calibrated or newly proposed strategy must pass a strict promotion sequence:

1. discovery and fitting on train data;
2. threshold confirmation on validation data;
3. one-time evaluation on untouched final-test data;
4. rolling walk-forward stability checks;
5. fee, slippage, and execution sensitivity checks;
6. forward-paper validation;
7. eligibility review under the existing historical-edge policy.

Possible promotion states:

```text
RESEARCH_ONLY
PROMISING
VALIDATED_BACKTEST
VALIDATED_OUT_OF_SAMPLE
VALIDATED_FORWARD_PAPER
PRODUCTION_ELIGIBLE
DEGRADED
REJECTED
```

No strategy may become funded-eligible merely because it achieved a high train-set score.

## Anti-overfitting requirements

The learning system must reject misleading improvement caused by memorization or excessive search.

Mandatory protections:

- chronological train, validation, and final-test separation;
- no future-candle features at decision time;
- no final-test-driven parameter changes;
- minimum sample-size requirements;
- stability across symbols and time periods;
- performance by regime, not only aggregate performance;
- explicit fee and slippage sensitivity;
- penalties for excessive parameter count and fragile rule complexity;
- tracking of every candidate tested, including rejected candidates;
- multiple-comparison controls or conservative promotion thresholds;
- walk-forward evaluation rather than one fixed historical split only;
- degradation monitoring after promotion.

## Strategy-strengthening behavior

Apex should compare profitable and unprofitable instances of the same setup family and determine
which measurable conditions separated them.

Example research question:

```text
Did high-relative-volume breakout setups with a shallow 1m pullback, rising 3m momentum,
and a successful VWAP reclaim outperform direct extended breakouts without a retest?
```

The result should become structured evidence such as:

- sample counts;
- expectancy;
- profit factor;
- maximum drawdown;
- favorable and adverse excursion distributions;
- target and stop probabilities;
- holding-time distribution;
- regime sensitivity;
- symbol sensitivity;
- out-of-sample stability.

Apex should strengthen strategies using these generalizable relationships, not by memorizing exact
dates or candle sequences.

## Implementation preference

Initial learning should remain deterministic, explainable, and configuration driven.

Recommended order:

1. rule-based historical replay;
2. structured feature and outcome capture;
3. deterministic calibration and grid or bounded search;
4. interpretable pattern mining;
5. optional machine-learning ranking only after the deterministic baseline is proven.

Machine learning may later rank or classify candidates, but it must not bypass structural risk,
entry, liquidation, account-policy, evidence-quality, or lifecycle constraints.

## Non-goals for the immediate next batch

The immediate N4.7 batch must not yet:

- invent new strategies automatically;
- tune thresholds using validation or final-test data;
- use opaque black-box models;
- promote strategies to funded eligibility;
- perform live, testnet, or real-money execution;
- claim profitability from the successful N4.6 dataset acquisition.

The immediate next step remains deterministic historical signal generation from the verified
multi-timeframe datasets.
