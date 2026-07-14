# N4.6.1 — Aligned Multi-Timeframe Historical Coverage Repair

## Status

Required correction before N4.7 historical signal generation.

## Problem discovered

The N4.6 campaign successfully acquired equal candle counts for each timeframe, but equal counts do not represent equal historical periods.

For example, 10,000 candles represent approximately:

- 1m: 6.9 days;
- 3m: 20.8 days;
- 5m: 34.7 days;
- 15m: 104 days;
- 30m: 208 days;
- 1h: 416 days;
- 4h: 1,666 days.

The existing train, validation, and final-test splits are count-based inside each independent dataset. Their timestamp boundaries therefore differ by timeframe.

Using those role files directly in one multi-timeframe historical decision would create one or more of these invalid conditions:

- stale higher-timeframe context;
- train data from one timeframe combined with validation or final-test dates from another;
- incomplete common coverage;
- very small higher-timeframe warmup inside the 1m common window;
- misleading no-lookahead claims despite role-boundary leakage.

N4.7 must not proceed on those misaligned split files.

## Required repair

Introduce timestamp-aligned campaign acquisition and splitting.

### Acquisition contract

The campaign must freeze a common historical period rather than one shared candle count.

Required fields:

- campaign ID;
- symbol set;
- timeframe set;
- provider;
- common start timestamp;
- common end timestamp;
- per-timeframe expected or maximum candle counts;
- warmup duration;
- output paths and dataset IDs.

Each timeframe may contain a different candle count, but all datasets must cover the same frozen analysis period plus required pre-period warmup.

### Split contract

Train, validation, and final-test boundaries must be common timestamps shared by every timeframe.

A candle belongs to a decision split according to its decision timestamp, not according to an independent percentage of that timeframe's candle count.

Earlier candles may be available as read-only warmup context for a later split when they precede the decision timestamp. Outcomes and parameter fitting must remain confined to the appropriate split.

### Warmup rule

The highest timeframe determines the minimum required warmup period.

For example, a 200-candle 4h warmup requires at least 800 hours of pre-decision history. The acquisition planner must calculate this explicitly rather than assuming 200 candles on every timeframe cover the same duration.

### Verification

The aligned campaign verifier must reject:

- datasets that do not cover the frozen common decision interval;
- missing pre-period warmup;
- inconsistent split timestamps;
- decisions whose required timeframe prefix is unavailable;
- cross-split future leakage;
- mismatched symbols, providers, IDs, hashes, or paths;
- timeframe-specific count assumptions presented as common coverage.

## Revised sequence

1. N4.6.1 — aligned date-range acquisition and timestamp split boundaries;
2. execute and verify a corrected BTC/ETH multi-timeframe dataset campaign;
3. N4.7 — deterministic historical signal generation;
4. N4.8 — historical outcome labeling and chronological replay;
5. N4.9 onward — experience datasets, calibration, discovery, and promotion.

## Current N4.6 artifacts

The completed N4.6 artifacts remain valid independent candle datasets and prove provider acquisition, persistence, hashing, splitting, and execution behavior.

They must not be used as a directly aligned seven-timeframe train/validation/final-test signal campaign.

No profitability or historical-signal conclusion may be drawn from them.
