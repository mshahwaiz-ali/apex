# P1 Review CLI

The `apex paper p1-review` command creates the combined, hash-verified P1 review artifact from persisted evidence.

```bash
apex paper p1-review \
  --historical-profile data/paper_trading/historical-profile.json \
  --forward-profile data/paper_trading/forward-profile.json \
  --daily-report data/paper_trading/daily/2026-07-15.json \
  --paper-store data/paper_trading/trades.json \
  --historical-period-days 180 \
  --forward-period-days 30 \
  --validation-status INSUFFICIENT_SAMPLE \
  --minimum-closed-trades 100 \
  --output data/paper_trading/reviews/2026-07-15.json
```

The command verifies the daily report hash, loads explicit historical and forward edge profiles, compares compatible segment dimensions, audits the canonical paper-trade lifecycle store, and writes the existing deterministic P1 review artifact.

`--manual-execution-usable` must be supplied only after a real operator review. The resulting artifact always keeps `production_eligible` false; P1 forward validation does not authorize live-money execution.
