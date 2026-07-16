# P1 Paper Operations Status

Use the status command before and during unattended forward-paper collection:

```bash
apex paper operations-status
```

JSON output:

```bash
apex paper operations-status --output json
```

The command inspects:

- futures and spot scheduler freshness;
- current and stale lock files;
- latest provider-failure counts;
- open and closed paper samples by market;
- scheduler log counts;
- daily report and P1 review artifact counts.

By default, a scheduler run is considered fresh for 15 minutes and a lock is considered stale after 30 minutes. Both thresholds are configurable:

```bash
apex paper operations-status \
  --maximum-run-age-minutes 15 \
  --stale-lock-minutes 30
```

`scheduler_ready=true` means both spot and futures have recent runs and no stale locks. It does not establish profitability, sufficient forward samples, production eligibility, or real-money readiness.
