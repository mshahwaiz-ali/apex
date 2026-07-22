# Apex Batch 11C Forensic Summary

- Reports: **54**
- Shadow trades: **189**
- Shadow stops: **97**
- Shadow targets: **37**
- Stops reaching 1R: **72**
- Stops reaching 2R: **47**
- Stops reaching 3R: **27**
- Stops with HTF conflict: **20**

## Shadow outcomes

- `expired`: 7
- `missed_entry`: 48
- `stop`: 97
- `target`: 37

## Loss families

- `LOW_MFE_THEN_STOP`: 13
- `MEANINGFUL_MFE_THEN_STOP`: 29
- `MODERATE_MFE_THEN_STOP`: 17
- `NEAR_TARGET_REVERSAL`: 28
- `WEAK_FOLLOW_THROUGH`: 10

## Profile breakdown

- **environment**: 61 shadow trades; {'stop': 41, 'target': 11, 'missed_entry': 9}
- **micro**: 49 shadow trades; {'missed_entry': 26, 'expired': 6, 'stop': 10, 'target': 7}
- **standard**: 79 shadow trades; {'stop': 46, 'missed_entry': 13, 'target': 19, 'expired': 1}

## Strategy breakdown

- **breakout_continuation**: 9 trades; {'expired': 1, 'target': 1, 'stop': 7}; losses {'MEANINGFUL_MFE_THEN_STOP': 5, 'NEAR_TARGET_REVERSAL': 1, 'MODERATE_MFE_THEN_STOP': 1}
- **breakout_retest**: 21 trades; {'stop': 12, 'missed_entry': 4, 'target': 5}; losses {'MODERATE_MFE_THEN_STOP': 5, 'MEANINGFUL_MFE_THEN_STOP': 5, 'NEAR_TARGET_REVERSAL': 2}
- **compression_expansion**: 7 trades; {'stop': 5, 'missed_entry': 1, 'target': 1}; losses {'MODERATE_MFE_THEN_STOP': 2, 'NEAR_TARGET_REVERSAL': 2, 'MEANINGFUL_MFE_THEN_STOP': 1}
- **momentum_breakout**: 9 trades; {'stop': 3, 'target': 2, 'expired': 4}; losses {'MEANINGFUL_MFE_THEN_STOP': 2, 'MODERATE_MFE_THEN_STOP': 1}
- **trend_pullback**: 1 trades; {'stop': 1}; losses {'WEAK_FOLLOW_THROUGH': 1}
- **unknown**: 142 trades; {'stop': 69, 'target': 28, 'missed_entry': 43, 'expired': 2}; losses {'LOW_MFE_THEN_STOP': 13, 'WEAK_FOLLOW_THROUGH': 9, 'NEAR_TARGET_REVERSAL': 23, 'MEANINGFUL_MFE_THEN_STOP': 16, 'MODERATE_MFE_THEN_STOP': 8}
