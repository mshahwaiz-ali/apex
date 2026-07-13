"""Market category, gainer-state, and routing contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MarketCategory(StrEnum):
    NORMAL_MARKET = "NORMAL_MARKET"
    GAINER = "GAINER"


class ScannerMode(StrEnum):
    NORMAL = "normal"
    GAINERS = "gainers"
    ALL = "all"


class GainerState(StrEnum):
    FRESH_BREAKOUT = "FRESH_BREAKOUT"
    ACCELERATION = "ACCELERATION"
    CONTROLLED_CONTINUATION = "CONTROLLED_CONTINUATION"
    FIRST_EXHAUSTION = "FIRST_EXHAUSTION"
    DISTRIBUTION = "DISTRIBUTION"
    BREAKDOWN = "BREAKDOWN"
    FAILED_BREAKDOWN_BOUNCE = "FAILED_BREAKDOWN_BOUNCE"
    TERMINAL_EXTENSION = "TERMINAL_EXTENSION"
    CHAOTIC = "CHAOTIC"


class GainerStateInput(BaseModel):
    """Measurable state inputs for top-gainer classification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    return_24h_pct: float | None = None
    recent_return_pct: float | None = None
    relative_volume: float | None = Field(default=None, ge=0)
    range_expansion: float | None = Field(default=None, ge=0)
    close_location: float | None = Field(default=None, ge=0, le=1)
    ema_extension_pct: float | None = None
    support_break: bool = False
    failed_breakdown_bounce: bool = False

    @model_validator(mode="after")
    def validate_minimum_signal(self) -> Self:
        if (
            self.return_24h_pct is None
            and self.recent_return_pct is None
            and self.relative_volume is None
            and self.range_expansion is None
        ):
            raise ValueError("gainer state requires at least one measurable input")
        return self


class GainerStateResult(BaseModel):
    """Deterministic gainer-state classification with evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    state: GainerState
    evidence: tuple[str, ...]
    missing_optional_data: tuple[str, ...] = ()


class GainerStateThresholds(BaseModel):
    """Configurable thresholds for deterministic gainer-state classification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fresh_total_return_pct: float = Field(default=5.0, ge=0)
    fresh_recent_return_pct: float = Field(default=1.0, ge=0)
    fresh_relative_volume: float = Field(default=1.5, ge=0)
    acceleration_total_return_pct: float = Field(default=10.0, ge=0)
    acceleration_recent_return_pct: float = Field(default=3.0, ge=0)
    acceleration_relative_volume: float = Field(default=2.0, ge=0)
    acceleration_range_expansion: float = Field(default=1.5, ge=0)
    distribution_total_return_pct: float = Field(default=8.0, ge=0)
    distribution_relative_volume: float = Field(default=2.0, ge=0)
    distribution_close_location: float = Field(default=0.45, ge=0, le=1)
    first_exhaustion_close_location: float = Field(default=0.55, ge=0, le=1)
    first_exhaustion_range_expansion: float = Field(default=1.5, ge=0)
    terminal_ema_extension_pct: float = Field(default=35.0, ge=0)
    terminal_range_expansion: float = Field(default=4.0, ge=0)
    terminal_close_location: float = Field(default=0.25, ge=0, le=1)


def classify_gainer_state(
    inputs: GainerStateInput,
    *,
    thresholds: GainerStateThresholds | None = None,
) -> GainerStateResult:
    """Classify a gainer without treating every strong move as a short."""

    config = thresholds or GainerStateThresholds()
    missing = tuple(
        label
        for label, value in (
            ("return_24h_pct", inputs.return_24h_pct),
            ("recent_return_pct", inputs.recent_return_pct),
            ("relative_volume", inputs.relative_volume),
            ("range_expansion", inputs.range_expansion),
            ("close_location", inputs.close_location),
            ("ema_extension_pct", inputs.ema_extension_pct),
        )
        if value is None
    )
    recent = inputs.recent_return_pct or 0.0
    total = inputs.return_24h_pct or 0.0
    relative_volume = inputs.relative_volume or 0.0
    range_expansion = inputs.range_expansion or 0.0
    close_location = inputs.close_location if inputs.close_location is not None else 0.5
    ema_extension = abs(inputs.ema_extension_pct or 0.0)

    if inputs.failed_breakdown_bounce:
        return _gainer_result(
            GainerState.FAILED_BREAKDOWN_BOUNCE,
            missing,
            "support break failed and price bounced back",
        )
    if inputs.support_break and recent < 0:
        return _gainer_result(
            GainerState.BREAKDOWN,
            missing,
            "support break with negative momentum",
        )
    if ema_extension >= config.terminal_ema_extension_pct or (
        range_expansion >= config.terminal_range_expansion
        and close_location <= config.terminal_close_location
    ):
        return _gainer_result(
            GainerState.TERMINAL_EXTENSION,
            missing,
            "extension or range expansion is too extreme for safe chase",
        )
    if (
        total >= config.distribution_total_return_pct
        and recent < 0.0
        and relative_volume >= config.distribution_relative_volume
        and close_location < config.distribution_close_location
    ):
        return _gainer_result(
            GainerState.DISTRIBUTION,
            missing,
            "high-volume move is failing to hold near candle highs",
        )
    if (
        total >= config.distribution_total_return_pct
        and recent > 0.0
        and close_location < config.first_exhaustion_close_location
        and range_expansion >= config.first_exhaustion_range_expansion
    ):
        return _gainer_result(
            GainerState.FIRST_EXHAUSTION,
            missing,
            "momentum is positive but closes are weakening",
        )
    if (
        total >= config.acceleration_total_return_pct
        and recent >= config.acceleration_recent_return_pct
        and relative_volume >= config.acceleration_relative_volume
        and range_expansion >= config.acceleration_range_expansion
    ):
        return _gainer_result(
            GainerState.ACCELERATION,
            missing,
            "rapid return, volume, and range expansion align",
        )
    if (
        total >= config.fresh_total_return_pct
        and recent >= config.fresh_recent_return_pct
        and relative_volume >= config.fresh_relative_volume
    ):
        return _gainer_result(
            GainerState.FRESH_BREAKOUT,
            missing,
            "new expansion has constructive volume",
        )
    if total >= config.fresh_total_return_pct and recent >= 0.0:
        return _gainer_result(
            GainerState.CONTROLLED_CONTINUATION,
            missing,
            "gainer remains constructive without terminal expansion",
        )
    return _gainer_result(GainerState.CHAOTIC, missing, "insufficient orderly gainer evidence")


def _gainer_result(
    state: GainerState,
    missing: tuple[str, ...],
    reason: str,
) -> GainerStateResult:
    return GainerStateResult(state=state, evidence=(reason,), missing_optional_data=missing)
