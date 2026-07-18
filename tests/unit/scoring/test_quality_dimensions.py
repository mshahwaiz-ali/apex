from __future__ import annotations

from apex.scoring.quality_dimensions import derive_quality_dimensions
from apex.strategies.contracts import RawQualityMetrics


def _metrics(*, entry_quality: float, extension_penalty: float) -> RawQualityMetrics:
    return RawQualityMetrics(
        trend_alignment=0.82,
        structure_quality=0.86,
        entry_quality=entry_quality,
        momentum_quality=0.76,
        volume_quality=0.68,
        liquidity_quality=0.80,
        target_space_quality=0.74,
        extension_penalty=extension_penalty,
        conflict_penalty=0.10,
    )


def test_setup_quality_survives_weak_current_execution() -> None:
    strong_entry = derive_quality_dimensions(_metrics(entry_quality=0.88, extension_penalty=0.05))
    weak_entry = derive_quality_dimensions(_metrics(entry_quality=0.25, extension_penalty=0.80))

    assert strong_entry.setup_quality == weak_entry.setup_quality
    assert strong_entry.execution_quality > weak_entry.execution_quality
    assert strong_entry.overall_trade_quality > weak_entry.overall_trade_quality


def test_quality_dimensions_remain_bounded() -> None:
    dimensions = derive_quality_dimensions(_metrics(entry_quality=0.55, extension_penalty=0.30))

    for value in (
        dimensions.setup_quality,
        dimensions.execution_quality,
        dimensions.target_quality,
        dimensions.risk_quality,
        dimensions.overall_trade_quality,
    ):
        assert 0.0 <= value <= 100.0
