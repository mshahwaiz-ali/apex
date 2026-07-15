# Live Spot Universe Scanner

`apex spot-scan-live` scans a comma-separated cash-spot universe through the validated S6 live orchestration path.

```bash
apex spot-scan-live \
  --symbols BTCUSDT,ETHUSDT,SOLUSDT \
  --account tests/fixtures/spot_live/account.json \
  --candles 200 \
  --output data/spot-live-scan.json
```

The scanner normalizes symbols to uppercase, removes duplicates while preserving first occurrence, analyzes each symbol independently, and records provider or validation failures without aborting the remaining universe.

Ranking is deterministic and intentionally does not invent a numeric score. Results are ordered by:

1. executable bounded spot plan;
2. approved selected strategy;
3. selected-strategy evidence count;
4. symbol as the final stable tie-breaker.

Every ranked item contains the canonical spot-analysis payload. Failures contain only the symbol and normalized error message. Output is stable sorted JSON and the optional output file is byte-identical to stdout.

This command is research and paper-validation only. It does not place orders, mutate paper positions, use leverage or margin, calculate liquidation, borrow assets, or produce short-selling instructions.
