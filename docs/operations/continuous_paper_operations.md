# P1 Continuous Paper Operations

P1 now includes a provider-independent operational cycle for both futures and spot paper trades.

## Operational boundary

`run_paper_operation_cycle()` performs one deterministic cycle. It loads persisted paper trades, selects only the requested market type, orders supplied closed candles chronologically, advances eligible lifecycles, persists the complete trade set, and can generate the existing daily forward-paper report.

Scheduling and live market-data collection remain outside the paper-trading domain. A long-running process, cron job, or service may call the cycle repeatedly after collecting normalized closed candles. The function does not fabricate candles, request exchange data, place orders, or enable real-money execution.

## Spot and futures isolation

Every cycle must explicitly specify `spot` or `futures`. Trades belonging to the other market are preserved without modification. Missing or stale candles are reported through deterministic trade-ID lists rather than silently advancing a lifecycle.

## Persistence and reporting

The cycle uses `PaperTradeStore` as the canonical lifecycle store. It may also write a daily forward-paper report using the existing deterministic SHA-256 report implementation. Operational cycle summaries can be atomically written without silent overwrite.

## Continuous operation

Continuous operation means repeatedly invoking the deterministic cycle with newly closed candles. The orchestration layer intentionally does not own an infinite loop because deployment scheduling, provider retry policy, rate limiting, and process supervision belong to the application/runtime boundary.

## Remaining P1 evidence

This layer makes sustained paper operation possible, but it does not itself establish sufficient forward samples, acceptable deviation, manual execution usability, or production eligibility. Those decisions remain governed by forward-edge evaluation, deviation reports, lifecycle audits, and the combined P1 review artifact.
