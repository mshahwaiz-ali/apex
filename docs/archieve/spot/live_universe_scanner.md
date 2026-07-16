# Live Spot Universe Scanner

`apex spot-scan-live` evaluates measurable market eligibility before running the validated S6 live cash-spot orchestration path.

```bash
apex spot-scan-live \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT \
  --account tests/fixtures/spot_live/account.json \
  --mode eligible \
  --candles 200 \
  --output data/spot-live-scan.json
```

## Eligibility

Thresholds are loaded from `config/spot.yaml` and cover:

- minimum 24-hour quote volume;
- maximum midpoint bid/ask spread percentage;
- minimum closed `4h` candle count;
- candle-gap detection using exchange-boundary-aware open-time cadence;
- minimum ATR percentage;
- maximum downside volatility percentage;
- terminal extension relative to the configured ATR multiple;
- excluded symbols;
- optional minimum market age only when measurable age data is available and the threshold is enabled.

Required unavailable values reject conservatively. Market age is never fabricated. Provider failures remain separate from eligibility rejections.

## Modes

- `eligible`: only eligible symbols proceed to full S6 orchestration.
- `watchlist`: eligible symbols and symbols rejected only for reviewable extension, ATR, or explicitly required market-history conditions proceed.
- `all`: every successfully evaluated symbol proceeds, while rejected symbols remain visible in `ineligible`.

The payload separates `ranked`, `ineligible`, and `failures`. Every ineligible item contains the symbol, eligibility status, machine-readable reason codes, and the measurable metadata used in the decision.

Symbols are normalized to uppercase and deduplicated while preserving first occurrence. Ranking remains deterministic and does not invent a numeric score. Results are ordered by eligibility, executable bounded spot plan, approved selected strategy, selected-strategy evidence count, and symbol as the final stable tie-breaker.

Output is stable sorted JSON and the optional output file is byte-identical to stdout.

This command is research and paper-validation only. It does not place orders, mutate paper positions, use leverage or margin, calculate liquidation, borrow assets, or produce short-selling instructions.
