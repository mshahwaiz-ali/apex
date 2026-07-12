from datetime import UTC, datetime

import pytest

from apex.liquidity import (
    LiquiditySide,
    LiquiditySweep,
    LiquidityZone,
    LiquidityZoneStatus,
    LiquidityZoneType,
    SweepClassification,
)
from apex.structure import (
    BreakDirection,
    ConfirmationStatus,
    PivotStatus,
    SwingPoint,
    SwingType,
    TrendAnalysis,
    TrendDirection,
    TrendEvidence,
    classify_trend,
    detect_structure_breaks,
)


def _swing(*, time: datetime | None = None) -> SwingPoint:
    return SwingPoint(
        index=1,
        time=time or datetime(2026, 1, 1, tzinfo=UTC),
        price=100.0,
        kind=SwingType.HIGH,
        status=PivotStatus.CONFIRMED,
        left_window=1,
        right_window=1,
    )


def _zone() -> LiquidityZone:
    return LiquidityZone(
        side=LiquiditySide.BUY_SIDE,
        kind=LiquidityZoneType.PIVOT_HIGH,
        low=100.0,
        high=100.0,
        representative_price=100.0,
        source_pivot_indices=(1,),
        touch_count=1,
        created_index=1,
        last_touch_index=1,
        age=1,
        status=LiquidityZoneStatus.ACTIVE,
        strength=0.5,
    )


def test_swing_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _swing(time=datetime(2026, 1, 1))


def test_trend_rejects_non_finite_thresholds() -> None:
    with pytest.raises(ValueError, match="finite"):
        classify_trend((), strong_persistence=float("nan"))


def test_break_detection_rejects_non_finite_thresholds() -> None:
    with pytest.raises(ValueError, match="finite"):
        detect_structure_breaks((), (), minimum_close_distance=float("inf"))


def test_liquidity_zone_rejects_unsorted_duplicate_sources() -> None:
    with pytest.raises(ValueError, match="unique and sorted"):
        LiquidityZone(
            side=LiquiditySide.BUY_SIDE,
            kind=LiquidityZoneType.EQUAL_HIGHS,
            low=100.0,
            high=100.0,
            representative_price=100.0,
            source_pivot_indices=(2, 1, 1),
            touch_count=3,
            created_index=2,
            last_touch_index=1,
            age=1,
            status=LiquidityZoneStatus.ACTIVE,
            strength=0.5,
        )


def test_sweep_rejects_direction_inconsistent_with_zone_side() -> None:
    with pytest.raises(ValueError, match="direction"):
        LiquiditySweep(
            zone=_zone(),
            direction=BreakDirection.BEARISH,
            candle_index=2,
            candle_time=datetime(2026, 1, 1, tzinfo=UTC),
            penetration=0.01,
            close_recovery=0.01,
            classification=SweepClassification.CONFIRMED_SWEEP,
            confirmation=ConfirmationStatus.CONFIRMED,
        )


def test_trend_analysis_rejects_non_finite_strength() -> None:
    with pytest.raises(ValueError, match="finite"):
        TrendAnalysis(
            direction=TrendDirection.UNCERTAIN,
            strength=float("nan"),
            evidence=TrendEvidence(),
        )
