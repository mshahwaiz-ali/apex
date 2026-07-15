# Paper lifecycle health gates

Apex evaluates forward-paper operational reliability and viability through a deterministic policy boundary built on `PaperLifecycleAnalytics`.

## Purpose

The health gate answers four separate questions without conflating them:

1. Is the observed terminal sample large enough to review?
2. Is the paper pipeline operating reliably?
3. Are entry and lifecycle outcomes structurally acceptable?
4. Is realized performance available and above the configured floor?

The evaluator does not approve live execution. It provides evidence for the forward-paper viability review defined in the project production gates.

## Stable statuses

```text
insufficient_sample
healthy
degraded
failed
```

Status precedence is deterministic:

1. `failed` when a hard operational reliability limit is exceeded;
2. `insufficient_sample` when no hard failure exists but the terminal sample is too small;
3. `degraded` when the sample is sufficient but lifecycle or performance quality is below policy;
4. `healthy` when all configured gates pass.

A hard operational failure takes precedence over an insufficient sample. This prevents a small, unreliable run from being mislabeled as merely incomplete.

## Machine-readable reasons

```text
insufficient_terminal_sample
provider_failure_rate_exceeded
missing_candle_rate_exceeded
persistence_failure_rate_exceeded
invalidation_rate_exceeded
unfilled_terminal_rate_exceeded
average_r_below_minimum
net_pnl_below_minimum
realized_performance_unavailable
```

Reasons are sorted deterministically in every report.

## Default policy

`PaperLifecycleHealthPolicy` defaults to:

| Gate | Default |
|---|---:|
| Minimum terminal trades | 20 |
| Maximum provider failure rate | 10% |
| Maximum missing-candle rate | 10% |
| Maximum persistence failure rate | 2% |
| Maximum invalidation rate | 25% |
| Maximum unfilled-terminal rate | 40% |
| Minimum average realized R | 0.0R |
| Minimum realized net PnL | 0.0 |
| Require realized performance | Yes |

All rate thresholds are inclusive: a value equal to its configured maximum passes; only a value above the maximum fails the gate.

## Explicit denominators

Rates use stable denominators:

| Rate | Numerator | Denominator |
|---|---|---|
| Provider failure | Provider failures | Requested symbols |
| Missing candle | Missing-candle trades | Loaded trades |
| Persistence failure | Persistence failures | Accepted plus persistence-failed intake records |
| Invalidation | Invalidations | Terminal trades |
| Unfilled terminal | Unfilled terminal trades | Terminal trades |

A zero denominator produces `0.0`. This avoids undefined arithmetic and does not invent negative evidence.

## Missing performance data

Missing realized PnL or average realized R remains `null` in analytics. When `require_realized_performance` is enabled, the health report emits:

```text
realized_performance_unavailable
```

It does not substitute zero and does not silently pass the performance gate.

## Review readiness

`PaperLifecycleHealthReport.ready_for_forward_viability_review` is true only for:

```text
healthy
degraded
```

It is false for failed or insufficient-sample reports. A degraded report may be reviewed because it contains enough evidence, but it is not equivalent to a healthy result.

## Public functions

```python
from apex.application.paper_lifecycle_health import (
    PaperLifecycleHealthPolicy,
    evaluate_paper_lifecycle_health,
    paper_lifecycle_health_payload,
)
```

The payload helper returns a stable JSON-ready mapping containing status, reasons, rates, counts, realized performance, and sample shortfall.

## Non-goals

The health evaluator does not:

- infer outcomes from free-text notes;
- fabricate liquidation events;
- replace historical-versus-forward comparison;
- optimize policy thresholds automatically;
- authorize testnet or live execution;
- bypass the separate execution-readiness gate.
