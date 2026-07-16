# P1 Unattended Daily Reporting

The `apex paper scheduled-daily-report` command creates the immutable report for the previous completed UTC day.

```bash
apex paper scheduled-daily-report
```

An explicit UTC date may be supplied for controlled backfilling:

```bash
apex paper scheduled-daily-report --report-date 2026-07-15
```

Reports are stored under `data/paper_trading/daily/YYYY-MM-DD.json`. If the report already exists, Apex verifies its payload hash and exits successfully without rewriting it. A mismatched or tampered artifact fails explicitly.

Systemd templates are provided in:

- `deploy/systemd/apex-paper-daily.service`
- `deploy/systemd/apex-paper-daily.timer`

The timer runs at 00:10 UTC and uses `Persistent=true`, so a missed run is executed when the machine becomes available again.
