"""Leakage-safe historical replay through the canonical spot analysis stack."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from apex.application.spot_analysis import spot_analysis_result_to_payload
from apex.application.spot_historical_dataset import (
    SpotHistoricalDatasetManifest,
    hash_spot_historical_rows,
    load_spot_historical_rows,
)
from apex.application.spot_live import _evidence, _snapshot
from apex.application.spot_orchestration import (
    SpotOrchestrationInput,
    _select_thesis_timeframe,
    analyze_spot_orchestration,
)
from apex.application.spot_structure import analyze_spot_structure, classify_spot_market_regime
from apex.config.spot import SpotProductConfig
from apex.config.spot_strategies import SpotStrategyConfig
from apex.data.resampling import resample_candles
from apex.domain.models import Candle
from apex.domain.spot import SpotAccountInput
from apex.domain.spot_market import (
    SpotEligibilityReason,
    SpotEligibilityThresholds,
    SpotMarketBreadthSnapshot,
    SpotMarketMetadata,
)
from apex.domain.spot_structure import SpotRegimeInput

SPOT_HISTORICAL_REPLAY_SCHEMA_VERSION = 1


class SpotHistoricalEligibilityResult(BaseModel):
    """Historical eligibility with explicit unavailable-field disclosure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    eligible: bool
    reasons: tuple[str, ...]
    unavailable_fields: tuple[str, ...] = ()


class SpotHistoricalReplayManifest(BaseModel):
    """Immutable manifest for one historical spot signal replay."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = SPOT_HISTORICAL_REPLAY_SCHEMA_VERSION
    campaign_id: str
    source_dataset_id: str
    source_dataset_sha256: str
    configuration_sha256: str
    records_sha256: str
    decision_count: int = Field(ge=1)
    accepted_plan_count: int = Field(ge=0)
    eligibility_pass_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)


@dataclass(frozen=True, slots=True)
class SpotHistoricalReplayResult:
    manifest: SpotHistoricalReplayManifest
    records: tuple[dict[str, Any], ...]


def replay_spot_historical_dataset(
    *,
    campaign_id: str,
    dataset_records_path: Path,
    dataset_manifest_path: Path,
    account: SpotAccountInput,
    product_config: SpotProductConfig,
    strategy_config: SpotStrategyConfig,
    warmup_candles_4h: int = 180,
) -> SpotHistoricalReplayResult:
    """Replay every common 4h close using only candles closed by that timestamp."""

    normalized_campaign = campaign_id.strip()
    if not normalized_campaign:
        raise ValueError("historical spot replay campaign id cannot be blank")
    if warmup_candles_4h < 180:
        raise ValueError("historical spot replay requires at least 180 4h warmup candles")

    rows = load_spot_historical_rows(dataset_records_path)
    manifest = SpotHistoricalDatasetManifest.model_validate_json(
        dataset_manifest_path.read_text(encoding="utf-8")
    )
    if hash_spot_historical_rows(rows) != manifest.dataset_sha256:
        raise ValueError("historical spot dataset hash does not match its manifest")
    if "4h" not in manifest.timeframes:
        raise ValueError("historical spot replay requires a 4h source timeframe")
    if "BTCUSDT" not in manifest.symbols:
        raise ValueError("historical spot replay requires BTCUSDT for regime context")

    grouped = _group_candles(rows)
    decision_times = _common_decision_times(
        grouped=grouped,
        symbols=manifest.symbols,
        warmup_candles=warmup_candles_4h,
    )
    configuration_hash = _configuration_hash(
        account=account,
        product_config=product_config,
        strategy_config=strategy_config,
        warmup_candles_4h=warmup_candles_4h,
    )

    records: list[dict[str, Any]] = []
    accepted_plan_count = 0
    eligibility_pass_count = 0
    failure_count = 0
    for decision_time in decision_times:
        btc_candles = _visible(grouped[("BTCUSDT", "4h")], decision_time)
        btc_structure = _structure_from_4h(btc_candles)
        regime = classify_spot_market_regime(
            SpotRegimeInput(
                btc_trend=btc_structure.trend,
                btc_extension=btc_structure.extension,
                breadth=SpotMarketBreadthSnapshot(
                    advancing_assets=0,
                    declining_assets=0,
                    unchanged_assets=0,
                    percentage_above_trend=None,
                ),
            )
        )
        for symbol in manifest.symbols:
            try:
                candles_4h = _visible(grouped[(symbol, "4h")], decision_time)
                structure = _structure_from_4h(candles_4h)
                thesis_snapshot = _snapshot("12h", _resample_12h(candles_4h))
                current_price = candles_4h[-1].close
                canonical_thesis = _select_thesis_timeframe(structure)
                recovery, deeper_support = _historical_support_geometry(
                    current_price=current_price,
                    canonical_support_lower=canonical_thesis.support.lower,
                    recovery_reference=thesis_snapshot.ema_fast,
                    atr=thesis_snapshot.atr,
                )

                eligibility = _historical_eligibility(
                    symbol=symbol,
                    candles=candles_4h,
                    product_config=product_config,
                )
                analysis = analyze_spot_orchestration(
                    SpotOrchestrationInput(
                        symbol=symbol,
                        current_price=current_price,
                        structure=structure,
                        regime=regime,
                        account=account,
                        evidence=_evidence(_resample_12h(candles_4h)),
                        deeper_support_price=deeper_support,
                        recovery_entry_price=recovery,
                    ),
                    product_config=product_config,
                    strategy_config=strategy_config,
                )
                payload = spot_analysis_result_to_payload(analysis)
                has_plan = analysis.planning is not None
                accepted_plan_count += int(has_plan)
                eligibility_pass_count += int(eligibility.eligible)
                records.append(
                    {
                        "schema_version": SPOT_HISTORICAL_REPLAY_SCHEMA_VERSION,
                        "campaign_id": normalized_campaign,
                        "symbol": symbol,
                        "decision_time": decision_time.isoformat(),
                        "source_dataset_sha256": manifest.dataset_sha256,
                        "configuration_sha256": configuration_hash,
                        "eligibility": eligibility.model_dump(mode="json"),
                        "eligibility_data_complete": not eligibility.unavailable_fields,
                        "unavailable_historical_fields": list(eligibility.unavailable_fields),
                        "analysis": payload,
                        "failure": None,
                    }
                )
            except (KeyError, TypeError, ValueError) as exc:
                failure_count += 1
                records.append(
                    {
                        "schema_version": SPOT_HISTORICAL_REPLAY_SCHEMA_VERSION,
                        "campaign_id": normalized_campaign,
                        "symbol": symbol,
                        "decision_time": decision_time.isoformat(),
                        "source_dataset_sha256": manifest.dataset_sha256,
                        "configuration_sha256": configuration_hash,
                        "eligibility": None,
                        "eligibility_data_complete": False,
                        "unavailable_historical_fields": ["bid_ask_spread"],
                        "analysis": None,
                        "failure": str(exc),
                    }
                )

    if not records:
        raise ValueError("historical spot replay produced no decision records")
    records_hash = _records_hash(records)
    replay_manifest = SpotHistoricalReplayManifest(
        campaign_id=normalized_campaign,
        source_dataset_id=manifest.dataset_id,
        source_dataset_sha256=manifest.dataset_sha256,
        configuration_sha256=configuration_hash,
        records_sha256=records_hash,
        decision_count=len(records),
        accepted_plan_count=accepted_plan_count,
        eligibility_pass_count=eligibility_pass_count,
        failure_count=failure_count,
    )
    return SpotHistoricalReplayResult(manifest=replay_manifest, records=tuple(records))


def write_spot_historical_replay(
    *,
    result: SpotHistoricalReplayResult,
    records_path: Path,
    manifest_path: Path,
    force: bool = False,
) -> None:
    """Persist deterministic JSONL records and the replay manifest atomically."""

    for path in (records_path, manifest_path):
        if path.exists() and not force:
            raise FileExistsError(f"refusing to overwrite historical spot replay file: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    records_text = "".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        for record in result.records
    )
    _atomic_write(records_path, records_text)
    _atomic_write(
        manifest_path,
        json.dumps(result.manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
    )


def _group_candles(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], tuple[Candle, ...]]:
    grouped: dict[tuple[str, str], list[Candle]] = defaultdict(list)
    for row in rows:
        candle = Candle.model_validate(row)
        grouped[(candle.symbol.upper(), candle.timeframe)].append(candle)
    return {
        key: tuple(sorted(values, key=lambda candle: candle.open_time))
        for key, values in grouped.items()
    }


def _common_decision_times(
    *,
    grouped: Mapping[tuple[str, str], Sequence[Candle]],
    symbols: Sequence[str],
    warmup_candles: int,
) -> tuple[datetime, ...]:
    common: set[datetime] | None = None
    for symbol in symbols:
        series = grouped.get((symbol, "4h"))
        if series is None or len(series) < warmup_candles:
            raise ValueError(f"insufficient 4h history for historical replay: {symbol}")
        closes = {candle.close_time for candle in series[warmup_candles - 1 :]}
        common = closes if common is None else common & closes
    if not common:
        raise ValueError("historical spot symbols have no common replay timestamps")
    return tuple(sorted(common))


def _visible(candles: Sequence[Candle], decision_time: datetime) -> tuple[Candle, ...]:
    visible = tuple(candle for candle in candles if candle.close_time <= decision_time)
    if len(visible) < 180:
        raise ValueError("historical spot replay window has insufficient visible 4h candles")
    return visible


def _resample_12h(candles: Sequence[Candle]) -> tuple[Candle, ...]:
    values = tuple(
        candle
        for candle in resample_candles(
            candles,
            source_timeframe="4h",
            target_timeframe="12h",
        )
        if candle.is_closed
    )
    if len(values) < 60:
        raise ValueError("historical spot replay requires at least 60 closed 12h candles")
    return values


def _structure_from_4h(candles: Sequence[Candle]):  # type: ignore[no-untyped-def]
    values_12h = _resample_12h(candles)
    return analyze_spot_structure(
        (
            _snapshot("12h", values_12h),
            _snapshot("4h", candles[-200:]),
        )
    )


def _historical_eligibility(
    *,
    symbol: str,
    candles: Sequence[Candle],
    product_config: SpotProductConfig,
) -> SpotHistoricalEligibilityResult:
    recent = candles[-200:]
    snapshot = _snapshot("4h", recent)
    quote_volume_24h = sum(candle.close * candle.volume for candle in recent[-6:])
    downside_values = [
        min((current.close - previous.close) / previous.close * 100, 0.0)
        for previous, current in zip(recent[-21:-1], recent[-20:], strict=True)
    ]
    downside = (
        sum(value * value for value in downside_values) / len(downside_values)
    ) ** 0.5
    interval = recent[1].open_time - recent[0].open_time
    has_gaps = any(
        current.open_time - previous.open_time != interval
        for previous, current in zip(recent[:-1], recent[1:], strict=True)
    )
    quote_asset = account_quote = "USDT"
    if not symbol.endswith(account_quote):
        quote_asset = symbol[-4:]
    metadata = SpotMarketMetadata(
        symbol=symbol,
        base_asset=symbol[: -len(quote_asset)],
        quote_asset=quote_asset,
        quote_volume_24h=quote_volume_24h,
        spread_percentage=None,
        market_age_days=None,
        available_candle_count=len(recent),
        has_data_gaps=has_gaps,
        atr_percentage=snapshot.atr / snapshot.close * 100,
        downside_volatility_percentage=downside,
        terminal_extension=(snapshot.close - snapshot.ema_fast) / snapshot.atr
        >= product_config.structure.terminal_extension_atr_multiple,
    )
    return _evaluate_historical_eligibility(metadata, product_config.eligibility)


def _evaluate_historical_eligibility(
    metadata: SpotMarketMetadata,
    thresholds: SpotEligibilityThresholds,
) -> SpotHistoricalEligibilityResult:
    """Evaluate measurable historical fields without fabricating spread observations."""

    reasons: list[str] = []
    if metadata.symbol.upper() in {symbol.upper() for symbol in thresholds.excluded_symbols}:
        reasons.append(SpotEligibilityReason.EXCLUDED_SYMBOL.value)
    if metadata.quote_volume_24h < thresholds.minimum_quote_volume_24h:
        reasons.append(SpotEligibilityReason.INSUFFICIENT_QUOTE_VOLUME.value)
    if thresholds.minimum_market_age_days is not None and (
        metadata.market_age_days is None
        or metadata.market_age_days < thresholds.minimum_market_age_days
    ):
        reasons.append(SpotEligibilityReason.INSUFFICIENT_MARKET_HISTORY.value)
    if (
        metadata.spread_percentage is not None
        and metadata.spread_percentage > thresholds.maximum_spread_percentage
    ):
        reasons.append(SpotEligibilityReason.SPREAD_TOO_WIDE.value)
    if metadata.available_candle_count < thresholds.minimum_candle_count:
        reasons.append(SpotEligibilityReason.INSUFFICIENT_CANDLE_HISTORY.value)
    if metadata.has_data_gaps:
        reasons.append(SpotEligibilityReason.DATA_GAPS.value)
    if metadata.terminal_extension:
        reasons.append(SpotEligibilityReason.TERMINAL_EXTENSION.value)
    if (
        metadata.atr_percentage is None
        or metadata.atr_percentage < thresholds.minimum_atr_percentage
    ):
        reasons.append(SpotEligibilityReason.INSUFFICIENT_ATR.value)
    if (
        metadata.downside_volatility_percentage is None
        or metadata.downside_volatility_percentage
        > thresholds.maximum_downside_volatility_percentage
    ):
        reasons.append(SpotEligibilityReason.DOWNSIDE_VOLATILITY_TOO_HIGH.value)

    return SpotHistoricalEligibilityResult(
        eligible=not reasons,
        reasons=tuple(reasons) if reasons else (SpotEligibilityReason.ELIGIBLE.value,),
        unavailable_fields=("bid_ask_spread",) if metadata.spread_percentage is None else (),
    )


def _historical_support_geometry(
    *,
    current_price: float,
    canonical_support_lower: float,
    recovery_reference: float,
    atr: float,
) -> tuple[float, float]:
    """Derive replay entries from canonical thesis support with strict separation."""

    if min(current_price, canonical_support_lower, recovery_reference, atr) <= 0:
        raise ValueError("historical support geometry inputs must be positive")
    buffer = max(atr * 0.01, current_price * 1e-8, 1e-8)
    recovery = min(current_price, recovery_reference)
    upper_bound = min(current_price, canonical_support_lower, recovery)
    deeper_support = upper_bound - max(atr, buffer)
    if deeper_support <= 0:
        deeper_support = upper_bound - buffer
    if deeper_support <= 0 or deeper_support >= upper_bound:
        raise ValueError("historical replay cannot derive valid support geometry")
    return recovery, deeper_support


def _configuration_hash(
    *,
    account: SpotAccountInput,
    product_config: SpotProductConfig,
    strategy_config: SpotStrategyConfig,
    warmup_candles_4h: int,
) -> str:
    payload = {
        "account": account.model_dump(mode="json"),
        "product_config": product_config.model_dump(mode="json"),
        "strategy_config": strategy_config.model_dump(mode="json"),
        "warmup_candles_4h": warmup_candles_4h,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _records_hash(records: Sequence[Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(json.dumps(record, sort_keys=True, separators=(",", ":")).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
