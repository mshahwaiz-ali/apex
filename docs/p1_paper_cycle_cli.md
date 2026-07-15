# P1 Paper Cycle CLI

The `apex paper cycle` command runs one provider-backed paper-operation cycle for either futures or spot trades.

## Futures cycle

```bash
apex paper cycle --market-type futures --timeframe 5m --candles 80
```

## Spot cycle with reports

```bash
apex paper cycle \
  --market-type spot \
  --timeframe 5m \
  --candles 80 \
  --report-date 2026-07-15 \
  --daily-report data/paper_trading/daily/2026-07-15.json \
  --cycle-report data/paper_trading/cycles/2026-07-15T120000Z.json
```

The command loads the canonical paper-trade store, fetches each active matching symbol once, isolates provider failures by symbol, advances only with closed candles, persists the complete store atomically, and optionally writes deterministic daily and cycle reports.

It does not place exchange orders or enable live-money execution. Repeating the command through cron, systemd, or another supervisor provides continuous paper operation while leaving scheduling and retry policy outside the trading domain.
