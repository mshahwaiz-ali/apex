# Automatic Paper Opportunity Intake

Automatic intake connects approved scanner output to the existing local paper-trade store. It is
strictly paper-only: it does not submit, simulate submission of, or prepare exchange orders.

## Commands

Futures:

```bash
apex paper intake-futures \
  --symbols-file config/symbols.yaml \
  --mode normal \
  --risk-mode STANDARD \
  --wallet-balance 100 \
  --candles 200
```

Spot:

```bash
apex paper intake-spot \
  --symbols BTC/USDT,ETH/USDT \
  --account config/spot_account.example.json \
  --mode eligible \
  --candles 200
```

Both commands support `--output json` for scheduler integration. Their summaries include observed
candidates, accepted candidates, rejected candidates, duplicate skips, persistence failures, stable
reason counts, and created paper-trade IDs.

## Futures qualification

A futures opportunity is admitted only when:

- Phase 6 produced a risk-approved setup;
- futures planning produced an actionable, non-rejected plan;
- the canonical entry state is actionable;
- the setup is not invalidated, missed, expired, rejected, or no-trade.

The stored paper record preserves the futures plan, management plan, eligibility, strategy approval,
risk mode, account-policy snapshot, scanner category, gainer context, strategy routing, precision
entry, setup segment, source command, and source mode.

## Spot qualification

Spot intake remains a separate cash-funded long-only path. It requires:

- an approved spot strategy selection;
- a complete spot planning result;
- positive allocated capital and quantity;
- an actionable spot entry state.

It preserves spot strategy, eligibility, scanner metadata, entry legs, allocation, scale-in plan,
protective stop, target ladder, lifecycle, and setup segment. Futures leverage, liquidation, margin,
wallet exposure, and short-direction logic are not reused.

## Duplicate prevention

Each admitted opportunity receives a SHA-256 deduplication key derived from canonical market type,
symbol, strategy, direction, setup segment, and plan identity. The analysis wall-clock timestamp is
retained for audit but excluded from the deduplication key. Therefore a repeated scheduler run that
produces the same canonical plan returns `DUPLICATE_SKIPPED` instead of creating another trade.

## Scheduler safety and ordering

Futures and spot intake use separate exclusive lock files and the same stale-lock recovery protocol as
paper lifecycle cycles. Structured intake results are appended to separate JSONL scheduler logs.

Recommended order:

```text
futures intake -> futures lifecycle cycle
spot intake    -> spot lifecycle cycle
daily report   -> after both completed UTC-day lifecycle streams
```

For unattended operation, prefer the combined market pipeline described in
[`paper_operations_pipeline.md`](paper_operations_pipeline.md). It wraps intake and lifecycle
advancement in one market-specific lock and writes a single audit record, preventing a scheduler from
advancing lifecycle state while the corresponding intake stage is missing or overlapping.

Example cron sequence for separate commands:

```cron
*/5 * * * * cd /opt/apex && .venv/bin/apex paper intake-futures --output json >> data/paper_trading/cron-futures-intake.log 2>&1
1-59/5 * * * * cd /opt/apex && .venv/bin/apex paper scheduled-futures --timeframe 5m --candles 80 >> data/paper_trading/cron-futures-cycle.log 2>&1
*/15 * * * * cd /opt/apex && .venv/bin/apex paper intake-spot --symbols BTC/USDT,ETH/USDT --account config/spot_account.json --output json >> data/paper_trading/cron-spot-intake.log 2>&1
2-59/15 * * * * cd /opt/apex && .venv/bin/apex paper scheduled-spot --timeframe 5m --candles 80 >> data/paper_trading/cron-spot-cycle.log 2>&1
15 0 * * * cd /opt/apex && .venv/bin/apex paper scheduled-daily-report >> data/paper_trading/cron-daily-report.log 2>&1
```

Example systemd service command lines:

```ini
ExecStart=/opt/apex/.venv/bin/apex paper intake-futures --output json
ExecStart=/opt/apex/.venv/bin/apex paper intake-spot --symbols BTC/USDT,ETH/USDT --account /opt/apex/config/spot_account.json --output json
```

Use distinct service units and timers for futures intake, futures lifecycle, spot intake, spot
lifecycle, and daily reporting when not using the combined pipeline. Set lifecycle timers after their
corresponding intake timers.

## Operations readiness

`apex paper operations-status` exposes separate cycle, intake, and pipeline freshness. The stronger
`operations_ready` result requires all three stages to be fresh for both markets and rejects stale
locks. `scheduler_ready` remains available as the narrower lifecycle-cycle health signal.

## Known limitations

- Intake depends on current public-provider data quality and never fabricates missing data.
- The JSON paper store is atomically replaced but is not a multi-process transactional database;
  scheduler locks are therefore mandatory for unattended operation.
- A changed canonical plan identity is treated as a new opportunity even for the same symbol.
- Automatic intake does not establish profitability, funded eligibility, or production readiness.
- Real-money and testnet order placement are outside this subsystem.
