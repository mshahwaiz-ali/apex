# Apex Batch 0 — Defect-Origin Matrix

Generated from committed baseline JSON. Runtime decisions are unchanged.

| symbol | candidate_id | candidate_outcome | entry_status | entry_mode | cmp_inside_zone | tp1_rr | score | execution_quality | provisional | confirmation_incomplete | htf_conflict | extended | executable_now | methodology_action | primary_blocker |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CLO/USDT | breakout_continuation:short:0 | rejected_below_score_threshold | PULLBACK_PREFERRED | retest | no | 17.8901 | 30.3026 | 20.692 | yes | no | no | yes | no | — | score 30.30 is below aggressive floor 52.00 |
| CLO/USDT | momentum_breakout:long:0 | rejected_below_score_threshold | WATCH_NEAR_ENTRY | market_near | yes | 0.5836 | 48.23 | 100 | yes | yes | yes | no | no | — | score 48.23 is below aggressive floor 52.00 |
| ERA/USDT | momentum_breakout:long:0 | accepted_with_conflict_warning | AGGRESSIVE_NOW | momentum_continuation | no | 3.3277 | 69.7289 | 94.3512 | yes | yes | yes | no | yes | allow | qualified provisional evidence accepted with penalty |
| ERA/USDT | momentum_breakout:long:0 | developing_setup | AGGRESSIVE_NOW | momentum_continuation | no | 2.8488 | 69.7289 | 94.3512 | yes | yes | yes | — | yes | — | — |
| HEI/USDT | breakout_retest:short:0 | rejected_below_score_threshold | PULLBACK_PREFERRED | retest | no | 2.6698 | 28.2723 | 36.3903 | yes | no | no | no | no | — | score 28.27 is below aggressive floor 52.00 |
| HEI/USDT | momentum_breakout:long:0 | rejected_below_score_threshold | WATCH_NEAR_ENTRY | market_near | yes | 0.3738 | 51.7283 | 100 | yes | yes | yes | no | no | — | score 51.73 is below aggressive floor 52.00 |
| VANRY/USDT | momentum_breakout:short:0 | rejected_below_score_threshold | WATCH_NEAR_ENTRY | market_near | yes | 0.094 | 46.9071 | 100 | yes | yes | no | no | no | — | score 46.91 is below aggressive floor 52.00 |

## Automatic contradiction flags

- **CLO/USDT · momentum_breakout:long:0:** 100 execution quality despite incomplete/provisional trigger; TP1 below 1R (0.584R).
- **ERA/USDT · momentum_breakout:long:0:** execution allowed with incomplete confirmation; execution allowed with provisional evidence; execution allowed while CMP is outside entry zone.
- **ERA/USDT · momentum_breakout:long:0:** execution allowed with incomplete confirmation; execution allowed with provisional evidence; execution allowed while CMP is outside entry zone.
- **HEI/USDT · momentum_breakout:long:0:** 100 execution quality despite incomplete/provisional trigger; TP1 below 1R (0.374R).
- **VANRY/USDT · momentum_breakout:short:0:** 100 execution quality despite incomplete/provisional trigger; TP1 below 1R (0.094R).
