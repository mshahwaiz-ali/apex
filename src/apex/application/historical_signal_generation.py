"""Chronological historical replay through the existing Apex analysis engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from apex.application.analysis import (
    analyze_symbol,
    serialize_symbol_analysis,
)
from apex.backtesting.historical_signal_campaign import (
    HistoricalSignalCampaignInputs,
    build_historical_signal_replay_points,
)
from apex.backtesting.historical_signal_replay import (
    HistoricalReplayProvider,
    HistoricalSignalSplit,
)
from apex.domain import GainerStateThresholds, MarketCategory
from apex.risk import DEFAULT_RISK_CONFIG, RiskConfig


@dataclass(frozen=True, slots=True)
class HistoricalSignalRecord:
    """One deterministic accepted, rejected, or failed replay decision."""

    campaign_id: str
    symbol: str
    decision_time: datetime
    split: HistoricalSignalSplit
    accepted: bool
    payload: Mapping[str, Any]
    source_dataset_hashes: tuple[str, ...]
    configuration_id: str | None
    feature_snapshot_references: Mapping[str, str]
    unavailable_optional_data: tuple[str, ...]
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.campaign_id.strip() or not self.symbol.strip():
            raise ValueError("historical signal record identity cannot be empty")
        if self.decision_time.tzinfo is None:
            raise ValueError("historical signal decision time must be timezone-aware")
        if not self.source_dataset_hashes:
            raise ValueError("historical signal record requires source dataset hashes")
        if self.accepted and self.failure_reason is not None:
            raise ValueError("accepted historical signal cannot contain a failure")

    def to_payload(self) -> dict[str, object]:
        """Return stable manifest-ready record content."""

        return {
            "campaign_id": self.campaign_id,
            "symbol": self.symbol,
            "decision_time": self.decision_time.isoformat(),
            "split": self.split.value,
            "accepted": self.accepted,
            "configuration_id": self.configuration_id,
            "feature_snapshot_references": dict(self.feature_snapshot_references),
            "unavailable_optional_data": list(self.unavailable_optional_data),
            "source_dataset_hashes": list(self.source_dataset_hashes),
            "failure_reason": self.failure_reason,
            "analysis": dict(self.payload),
        }


@dataclass(frozen=True, slots=True)
class HistoricalSignalGenerationResult:
    """In-memory chronological replay result before persistence."""

    campaign_id: str
    records: tuple[HistoricalSignalRecord, ...]

    def __post_init__(self) -> None:
        if not self.campaign_id.strip():
            raise ValueError("historical signal result campaign ID cannot be empty")
        if not self.records:
            raise ValueError("historical signal generation produced no records")

        keys = tuple((record.decision_time, record.symbol) for record in self.records)
        if keys != tuple(sorted(keys)):
            raise ValueError("historical signal records must be chronological")

    @property
    def accepted_count(self) -> int:
        return sum(record.accepted for record in self.records)

    @property
    def rejected_count(self) -> int:
        return len(self.records) - self.accepted_count


def generate_historical_signals(
    *,
    inputs: HistoricalSignalCampaignInputs,
    timeframe_roles: Mapping[str, str] | None = None,
    timeframe_max_staleness_seconds: Mapping[str, int] | None = None,
    candle_limit: int = 200,
    risk_config: RiskConfig = DEFAULT_RISK_CONFIG,
    scanner_type: MarketCategory = MarketCategory.NORMAL_MARKET,
    strategy_routing: Mapping[str, Sequence[str]] | None = None,
    gainer_state_thresholds: GainerStateThresholds | None = None,
) -> HistoricalSignalGenerationResult:
    """Replay the existing deterministic analysis stack without future data."""

    if candle_limit < 40:
        raise ValueError("historical signal generation requires at least 40 candles")

    points = build_historical_signal_replay_points(inputs)
    records: list[HistoricalSignalRecord] = []

    for point in points:
        for symbol in inputs.symbols:
            provider = HistoricalReplayProvider(
                store=inputs.store,
                decision_time=point.decision_time,
                source_name=(f"historical_replay:{inputs.campaign_id}"),
            )
            symbol_hashes = tuple(
                dataset.content_hash
                for dataset in inputs.source_datasets
                if dataset.symbol == symbol
            )

            try:
                analysis = analyze_symbol(
                    symbol,
                    provider,
                    timeframes=inputs.timeframes,
                    timeframe_roles=timeframe_roles,
                    timeframe_max_staleness_seconds=(timeframe_max_staleness_seconds),
                    candle_limit=candle_limit,
                    risk_config=risk_config,
                    generated_at=point.decision_time,
                    scanner_type=scanner_type,
                    strategy_routing=strategy_routing,
                    gainer_state_thresholds=gainer_state_thresholds,
                )
                payload = serialize_symbol_analysis(analysis)
                records.append(
                    build_historical_signal_record(
                        campaign_id=inputs.campaign_id,
                        symbol=symbol,
                        decision_time=point.decision_time,
                        split=point.split,
                        payload=payload,
                        source_dataset_hashes=symbol_hashes,
                    )
                )
            except Exception as exc:
                records.append(
                    HistoricalSignalRecord(
                        campaign_id=inputs.campaign_id,
                        symbol=symbol,
                        decision_time=point.decision_time,
                        split=point.split,
                        accepted=False,
                        payload={
                            "symbol": symbol,
                            "decision": "NO_TRADE",
                            "rejection_codes": ["historical_analysis_failure"],
                            "reasons": [str(exc)],
                        },
                        source_dataset_hashes=symbol_hashes,
                        configuration_id=None,
                        feature_snapshot_references={},
                        unavailable_optional_data=(
                            "ticker",
                            "order_book",
                            "exchange_filters",
                            "liquidation_clusters",
                            "funding_rate",
                            "open_interest",
                        ),
                        failure_reason=str(exc),
                    )
                )

    return HistoricalSignalGenerationResult(
        campaign_id=inputs.campaign_id,
        records=tuple(records),
    )


def build_historical_signal_record(
    *,
    campaign_id: str,
    symbol: str,
    decision_time: datetime,
    split: HistoricalSignalSplit,
    payload: Mapping[str, Any],
    source_dataset_hashes: tuple[str, ...],
) -> HistoricalSignalRecord:
    """Convert one serialized live-engine result into a historical record."""

    decision = str(payload.get("decision", "NO_TRADE"))
    accepted = decision in {"LONG", "SHORT"}

    raw_configuration_id = payload.get("configuration_id")
    configuration_id = str(raw_configuration_id) if raw_configuration_id is not None else None

    quality = payload.get("timeframe_data_quality")
    quality_by_timeframe = quality if isinstance(quality, Mapping) else {}

    feature_references: dict[str, str] = {}
    unavailable: set[str] = {
        "funding_rate",
        "open_interest",
    }

    for timeframe, raw_frame in quality_by_timeframe.items():
        if not isinstance(raw_frame, Mapping):
            continue

        last_closed_at = raw_frame.get("last_closed_at")
        if last_closed_at is not None:
            feature_references[str(timeframe)] = f"{symbol}:{timeframe}:{last_closed_at}"

        optional_fields = {
            "ticker_price": "ticker",
            "spread_percentage": "ticker_spread",
            "order_book_spread_percentage": "order_book",
            "order_book_depth_imbalance": "order_book",
            "exchange_tick_size": "exchange_filters",
            "exchange_step_size": "exchange_filters",
            "exchange_min_notional": "exchange_filters",
            "nearest_long_liquidation_distance_pct": ("liquidation_clusters"),
            "nearest_short_liquidation_distance_pct": ("liquidation_clusters"),
        }
        for field, label in optional_fields.items():
            if raw_frame.get(field) is None:
                unavailable.add(label)

    return HistoricalSignalRecord(
        campaign_id=campaign_id,
        symbol=symbol,
        decision_time=decision_time,
        split=split,
        accepted=accepted,
        payload=dict(payload),
        source_dataset_hashes=source_dataset_hashes,
        configuration_id=configuration_id,
        feature_snapshot_references=feature_references,
        unavailable_optional_data=tuple(sorted(unavailable)),
    )
