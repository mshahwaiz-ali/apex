"""Deterministic conversion of completed backtest trades into historical outcomes."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from apex.application.historical_edge import (
    DatasetPartition,
    HistoricalOutcome,
    MarketType,
)
from apex.backtesting import BacktestOutcome, SimulatedTrade


class OutcomeRejectionReason(StrEnum):
    """Auditable reasons why a simulated trade was not imported."""

    MISSED_ENTRY = "MISSED_ENTRY"
    MISSING_ENTRY_TIME = "MISSING_ENTRY_TIME"
    MISSING_EXECUTED_ENTRY_PRICE = "MISSING_EXECUTED_ENTRY_PRICE"
    MISSING_REGIME = "MISSING_REGIME"
    MISSING_MFE_R = "MISSING_MFE_R"
    MISSING_MAE_R = "MISSING_MAE_R"
    OUTSIDE_PARTITIONS = "OUTSIDE_PARTITIONS"
    PARTITION_SPAN = "PARTITION_SPAN"
    ZERO_NET_RESULT = "ZERO_NET_RESULT"
    INVALID_METRIC = "INVALID_METRIC"
    DUPLICATE_OUTCOME = "DUPLICATE_OUTCOME"


@dataclass(frozen=True, slots=True)
class OutcomeConversionRejection:
    source_index: int
    reason: OutcomeRejectionReason
    detail: str
    setup_id: str | None = None


@dataclass(frozen=True, slots=True)
class HistoricalOutcomeConversionSummary:
    dataset_id: str
    source_identity: str
    accepted_count: int
    rejected_count: int
    duplicate_count: int
    rejection_reasons: Mapping[str, int]
    outcomes: tuple[HistoricalOutcome, ...]
    rejections: tuple[OutcomeConversionRejection, ...]
    result_hash: str

    def __post_init__(self) -> None:
        if not self.dataset_id.strip() or not self.source_identity.strip():
            raise ValueError("dataset and source identities are required")
        if self.accepted_count != len(self.outcomes):
            raise ValueError("accepted count must match generated outcomes")
        if self.rejected_count != len(self.rejections):
            raise ValueError("rejected count must match rejections")
        if self.duplicate_count < 0:
            raise ValueError("duplicate count cannot be negative")
        _validate_sha256(self.result_hash)
        object.__setattr__(
            self, "rejection_reasons", MappingProxyType(dict(self.rejection_reasons))
        )


def convert_backtest_trades(
    trades: Sequence[SimulatedTrade],
    *,
    dataset_id: str,
    market_type: MarketType,
    partitions: Sequence[DatasetPartition],
    source_identity: str,
) -> HistoricalOutcomeConversionSummary:
    """Convert terminal entered trades without fabricating unavailable evidence.

    Split assignment uses actual entry time from trade metadata. A trade whose close
    falls after that partition's end is rejected to prevent cross-split leakage.
    """

    if not dataset_id.strip() or not source_identity.strip():
        raise ValueError("dataset and source identities are required")
    ordered_partitions = tuple(sorted(partitions, key=lambda item: item.start_at))
    outcomes: list[HistoricalOutcome] = []
    rejections: list[OutcomeConversionRejection] = []
    seen_setup_ids: set[str] = set()
    duplicate_count = 0

    for index, trade in enumerate(trades):
        outcome, rejection = _convert_trade(
            trade,
            source_index=index,
            dataset_id=dataset_id,
            market_type=market_type,
            partitions=ordered_partitions,
            source_identity=source_identity,
        )
        if rejection is not None:
            rejections.append(rejection)
            continue
        assert outcome is not None
        if outcome.setup_id in seen_setup_ids:
            duplicate_count += 1
            rejections.append(
                OutcomeConversionRejection(
                    source_index=index,
                    reason=OutcomeRejectionReason.DUPLICATE_OUTCOME,
                    detail="setup identity already occurred in this import",
                    setup_id=outcome.setup_id,
                )
            )
            continue
        seen_setup_ids.add(outcome.setup_id)
        outcomes.append(outcome)

    outcome_tuple = tuple(sorted(outcomes, key=lambda item: (item.opened_at, item.setup_id)))
    rejection_tuple = tuple(rejections)
    reason_counts = Counter(rejection.reason.value for rejection in rejection_tuple)
    payload = {
        "dataset_id": dataset_id,
        "source_identity": source_identity,
        "market_type": market_type.value,
        "outcomes": [_outcome_payload(item) for item in outcome_tuple],
        "rejections": [_rejection_payload(item) for item in rejection_tuple],
    }
    return HistoricalOutcomeConversionSummary(
        dataset_id=dataset_id,
        source_identity=source_identity,
        accepted_count=len(outcome_tuple),
        rejected_count=len(rejection_tuple),
        duplicate_count=duplicate_count,
        rejection_reasons=dict(sorted(reason_counts.items())),
        outcomes=outcome_tuple,
        rejections=rejection_tuple,
        result_hash=_stable_hash(payload),
    )


def score_band_from_confidence(confidence_score: float) -> str:
    """Map the existing 0-100 confidence score to documented deterministic bands."""

    if not math.isfinite(confidence_score) or not 0.0 <= confidence_score <= 100.0:
        raise ValueError("confidence score must be finite and between zero and 100")
    if confidence_score >= 85.0:
        return "85-100"
    if confidence_score >= 75.0:
        return "75-84"
    if confidence_score >= 65.0:
        return "65-74"
    if confidence_score >= 55.0:
        return "55-64"
    return "0-54"


def _convert_trade(
    trade: SimulatedTrade,
    *,
    source_index: int,
    dataset_id: str,
    market_type: MarketType,
    partitions: Sequence[DatasetPartition],
    source_identity: str,
) -> tuple[HistoricalOutcome | None, OutcomeConversionRejection | None]:
    if trade.outcome is BacktestOutcome.MISSED_ENTRY:
        return None, _reject(
            source_index, OutcomeRejectionReason.MISSED_ENTRY, "trade never entered"
        )

    entry_time = _metadata_datetime(trade.metadata, "entry_time")
    if entry_time is None:
        return None, _reject(
            source_index,
            OutcomeRejectionReason.MISSING_ENTRY_TIME,
            "actual entry_time is required in trade metadata",
        )
    entry_price = _metadata_float(trade.metadata, "executed_entry_price")
    if entry_price is None or entry_price <= 0.0:
        return None, _reject(
            source_index,
            OutcomeRejectionReason.MISSING_EXECUTED_ENTRY_PRICE,
            "positive executed_entry_price is required in trade metadata",
        )
    regime = str(trade.metadata.get("regime", "")).strip()
    if not regime:
        return None, _reject(
            source_index,
            OutcomeRejectionReason.MISSING_REGIME,
            "regime is required in trade metadata",
        )
    mfe_r = _metadata_float(trade.metadata, "maximum_favorable_excursion_r")
    if mfe_r is None:
        return None, _reject(
            source_index, OutcomeRejectionReason.MISSING_MFE_R, "MFE in R is required"
        )
    mae_r = _metadata_float(trade.metadata, "maximum_adverse_excursion_r")
    if mae_r is None:
        return None, _reject(
            source_index, OutcomeRejectionReason.MISSING_MAE_R, "MAE in R is required"
        )
    if not all(
        math.isfinite(value) for value in (mfe_r, mae_r, trade.net_pnl, trade.realized_r_multiple)
    ):
        return None, _reject(
            source_index, OutcomeRejectionReason.INVALID_METRIC, "trade metrics must be finite"
        )
    if trade.net_pnl == 0.0:
        return None, _reject(
            source_index,
            OutcomeRejectionReason.ZERO_NET_RESULT,
            "HistoricalOutcome currently supports win/loss results only",
        )

    partition = _partition_for_entry(entry_time, partitions)
    if partition is None:
        return None, _reject(
            source_index,
            OutcomeRejectionReason.OUTSIDE_PARTITIONS,
            "entry time is outside all declared partitions",
        )
    if trade.exit_time > partition.end_at:
        return None, _reject(
            source_index,
            OutcomeRejectionReason.PARTITION_SPAN,
            "trade closes after its entry partition ends",
        )

    setup_id = _setup_id(
        trade,
        dataset_id=dataset_id,
        source_identity=source_identity,
        entry_time=entry_time,
        entry_price=entry_price,
    )
    entry_notional = entry_price * trade.signal.quantity
    if not math.isfinite(entry_notional) or entry_notional <= 0.0:
        return None, _reject(
            source_index,
            OutcomeRejectionReason.INVALID_METRIC,
            "executed entry notional must be positive and finite",
            setup_id=setup_id,
        )
    return (
        HistoricalOutcome(
            setup_id=setup_id,
            dataset_id=dataset_id,
            split=partition.split,
            market_type=market_type,
            strategy=trade.signal.strategy.value,
            symbol=trade.signal.symbol,
            regime=regime,
            score_band=score_band_from_confidence(trade.signal.confidence_score),
            opened_at=entry_time,
            closed_at=trade.exit_time,
            net_return=trade.net_pnl / entry_notional,
            r_multiple=trade.realized_r_multiple,
            maximum_favorable_excursion_r=mfe_r,
            maximum_adverse_excursion_r=mae_r,
            won=trade.net_pnl > 0.0,
        ),
        None,
    )


def _partition_for_entry(
    entry_time: datetime, partitions: Sequence[DatasetPartition]
) -> DatasetPartition | None:
    return next(
        (
            partition
            for partition in partitions
            if partition.start_at <= entry_time < partition.end_at
        ),
        None,
    )


def _metadata_datetime(metadata: Mapping[str, object], key: str) -> datetime | None:
    value = metadata.get(key)
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _metadata_float(metadata: Mapping[str, object], key: str) -> float | None:
    value = metadata.get(key)
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _setup_id(
    trade: SimulatedTrade,
    *,
    dataset_id: str,
    source_identity: str,
    entry_time: datetime,
    entry_price: float,
) -> str:
    payload = {
        "dataset_id": dataset_id,
        "source_identity": source_identity,
        "symbol": trade.signal.symbol,
        "strategy": trade.signal.strategy.value,
        "direction": trade.signal.direction.value,
        "generated_at": trade.signal.generated_at.isoformat(),
        "entry_time": entry_time.isoformat(),
        "entry_price": entry_price,
        "stop_price": trade.signal.stop_price,
        "target_prices": trade.signal.target_prices,
    }
    return _stable_hash(payload)


def _reject(
    source_index: int,
    reason: OutcomeRejectionReason,
    detail: str,
    *,
    setup_id: str | None = None,
) -> OutcomeConversionRejection:
    return OutcomeConversionRejection(source_index, reason, detail, setup_id)


def _outcome_payload(outcome: HistoricalOutcome) -> dict[str, object]:
    return {
        "setup_id": outcome.setup_id,
        "dataset_id": outcome.dataset_id,
        "split": outcome.split.value,
        "market_type": outcome.market_type.value,
        "strategy": outcome.strategy,
        "symbol": outcome.symbol,
        "regime": outcome.regime,
        "score_band": outcome.score_band,
        "opened_at": outcome.opened_at.isoformat(),
        "closed_at": outcome.closed_at.isoformat(),
        "net_return": outcome.net_return,
        "r_multiple": outcome.r_multiple,
        "maximum_favorable_excursion_r": outcome.maximum_favorable_excursion_r,
        "maximum_adverse_excursion_r": outcome.maximum_adverse_excursion_r,
        "won": outcome.won,
    }


def _rejection_payload(rejection: OutcomeConversionRejection) -> dict[str, object]:
    return {
        "source_index": rejection.source_index,
        "reason": rejection.reason.value,
        "detail": rejection.detail,
        "setup_id": rejection.setup_id,
    }


def _stable_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _validate_sha256(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("result hash must be a SHA-256 hex digest")
