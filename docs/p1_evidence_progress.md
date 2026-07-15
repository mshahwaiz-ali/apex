# P1 Forward Evidence Progress

Use the evidence-progress command to inspect how much closed forward-paper evidence exists for each canonical setup segment.

```bash
apex paper evidence-progress --minimum-closed-trades 100
```

JSON output:

```bash
apex paper evidence-progress --minimum-closed-trades 100 --output json
```

The command groups terminal paper trades by the serialized `setup_segment`. Legacy records without that object fall back to market type, strategy, direction, and symbol.

For every segment it reports:

- closed trade count;
- remaining trades required by the configured sample threshold;
- sample sufficiency;
- win rate;
- expectancy in R;
- profit factor;
- maximum cumulative drawdown in R.

This command measures forward-paper evidence progress only. Reaching a sample threshold does not itself establish production or funded-account eligibility. Lifecycle audit, historical deviation, manual usability, and review gates remain mandatory.
