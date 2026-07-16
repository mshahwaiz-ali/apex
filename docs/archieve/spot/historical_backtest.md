# Historical Spot Backtest

## Purpose

`apex dataset spot-history-backtest` executes verified historical spot replay plans against later closed candles through one deterministic, chronological, shared cash wallet.

This is a research and paper-validation command. It does not place orders and does not establish profitability, funded eligibility, production readiness, or real-money safety.

## Required artifacts

The command requires the four artifacts produced by the historical spot dataset and replay stages:

- dataset JSONL records;
- dataset manifest JSON;
- replay JSONL records;
- replay manifest JSON.

The dataset and replay hashes are verified before execution. The replay manifest must reference the exact dataset hash.

## Example

```bash
apex dataset spot-history-backtest \
  --campaign-id s9-campaign \
  --dataset-records data/spot/history.jsonl \
  --dataset-manifest data/spot/history.manifest.json \
  --replay-records data/spot/replay.jsonl \
  --replay-manifest data/spot/replay.manifest.json \
  --result-output data/spot/backtest.json \
  --execution-manifest-output data/spot/backtest.manifest.json \
  --starting-cash 10000 \
  --fee-rate 0.001 \
  --slippage-rate 0.0005 \
  --maximum-position-allocation 0.25 \
  --maximum-total-exposure 0.80 \
  --maximum-open-positions 4 \
  --quote-reserve 0.10 \
  --entry-expiry-hours 48 \
  --maximum-holding-hours 720 \
  --ambiguous-candle-policy conservative
```

Existing outputs are not overwritten unless `--force` is supplied.

## Deterministic execution behavior

The runner:

- orders replay decisions by timestamp and symbol;
- selects the smallest available supported execution timeframe per symbol;
- uses only candles visible at each chronological timestamp;
- enforces a shared cash balance, quote reserve, total exposure, per-position allocation, open-position limit, and duplicate-symbol protection;
- models adverse entry and exit slippage plus fees;
- supports bounded scale-in entries and ordered partial targets;
- expires unfilled entries;
- invalidates entries whose structural invalidation is crossed before fill;
- rejects price beyond the maximum chase boundary;
- applies a maximum holding time and final end-of-dataset close;
- treats same-candle stop and target ambiguity conservatively by default.

The output includes chronological events, closed trades, an equity curve, portfolio metrics, and performance breakdowns by symbol, strategy, market regime, eligibility state, entry state, and exit reason.

## Persistence and integrity

The result JSON contains its deterministic `result_sha256`. The execution manifest binds:

- campaign ID;
- dataset hash;
- replay-record hash;
- replay-configuration hash;
- backtest-configuration hash;
- result hash;
- signal, eligibility, plan, fill, and trade counts;
- ending equity.

Both files are written atomically. The CLI immediately reloads them and verifies the result hash, provenance fields, summary counts, and ending equity before reporting completion.

Any tampering, malformed JSON, hash mismatch, provenance mismatch, or manifest/result summary mismatch fails explicitly.

## Validation boundary

S9 remains incomplete until the focused spot replay/backtest/CLI checks and the complete repository Ruff, strict mypy, and pytest quality gate are run locally and their actual outputs are recorded in `docs/implementation_progress.md`.
