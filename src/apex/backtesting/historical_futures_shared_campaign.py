"""Shared-wallet integration for verified historical futures campaigns."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from apex.application.historical_signal_io import load_historical_signal_record_payloads
from apex.backtesting.historical_futures_campaign import (
    HistoricalFuturesCampaignRequest,
    HistoricalFuturesCampaignResult,
    HistoricalFuturesExecutionManifest,
    HistoricalFuturesObservation,
    HistoricalFuturesTradeResult,
    execute_historical_futures_campaign,
    load_historical_futures_execution_manifest,
    write_historical_futures_campaign,
)
from apex.backtesting.historical_signal_campaign import HistoricalSignalCampaignInputs
from apex.backtesting.shared_wallet_replay import (
    SharedWalletConfig,
    SharedWalletReplayResult,
    WalletReplayCandidate,
    replay_shared_wallet,
)

SHARED_HISTORICAL_FUTURES_SCHEMA_VERSION: Final = 1
_MISSING_MARGIN_CODE: Final = "historical_required_margin_missing"


@dataclass(frozen=True, slots=True)
class SharedHistoricalFuturesCampaignResult:
    """Historical campaign result after shared-wallet admission controls."""

    campaign: HistoricalFuturesCampaignResult
    wallet: SharedWalletReplayResult
    wallet_config: SharedWalletConfig
    configuration_hash: str

    def to_payload(self) -> dict[str, object]:
        campaign_payload = self.campaign.to_payload()
        campaign_payload.update(
            {
                "schema_version": SHARED_HISTORICAL_FUTURES_SCHEMA_VERSION,
                "shared_wallet": {
                    "configuration": self.wallet_config.to_payload(),
                    "configuration_hash": self.configuration_hash,
                    "starting_equity": self.wallet.starting_equity,
                    "ending_equity": self.wallet.ending_equity,
                    "peak_equity": self.wallet.peak_equity,
                    "maximum_drawdown": self.wallet.maximum_drawdown,
                    "realized_pnl": self.wallet.realized_pnl,
                    "total_fees": self.wallet.total_fees,
                    "rejection_counts": dict(self.wallet.rejection_counts),
                    "equity_curve": [point.to_payload() for point in self.wallet.equity_curve],
                },
            }
        )
        return campaign_payload


@dataclass(frozen=True, slots=True)
class SharedHistoricalFuturesExecutionManifest:
    """Manifest extension binding account assumptions to campaign artifacts."""

    base: HistoricalFuturesExecutionManifest
    wallet_configuration_hash: str
    wallet_rejection_counts: tuple[tuple[str, int], ...]
    schema_version: int = SHARED_HISTORICAL_FUTURES_SCHEMA_VERSION

    def to_payload(self) -> dict[str, object]:
        payload = self.base.to_payload()
        payload.update(
            {
                "schema_version": self.schema_version,
                "wallet_configuration_hash": self.wallet_configuration_hash,
                "wallet_rejection_counts": dict(self.wallet_rejection_counts),
            }
        )
        return payload


def execute_shared_historical_futures_campaign(
    *,
    request: HistoricalFuturesCampaignRequest,
    inputs: HistoricalSignalCampaignInputs,
    wallet_config: SharedWalletConfig,
) -> SharedHistoricalFuturesCampaignResult:
    """Run canonical trade simulation, then admit trades onto one shared wallet."""

    isolated = execute_historical_futures_campaign(request=request, inputs=inputs)
    payloads = load_historical_signal_record_payloads(request.records_path)
    margin_by_key = _required_margin_by_key(payloads)
    candidates: list[WalletReplayCandidate] = []
    missing_margin_ids: set[str] = set()

    for item in isolated.trades:
        signal = item.trade.signal
        key = (signal.generated_at.isoformat(), signal.symbol)
        required_margin = margin_by_key.get(key)
        if required_margin is None:
            missing_margin_ids.add(item.result_id)
            continue
        candidates.append(
            WalletReplayCandidate(
                candidate_id=item.result_id,
                split=item.split.value,
                trade=item.trade,
                required_margin=required_margin,
            )
        )

    wallet = replay_shared_wallet(
        candidates=tuple(candidates),
        starting_equity=request.starting_equity,
        config=wallet_config,
    )
    accepted_ids = {item.candidate_id for item in wallet.accepted_candidates}
    rejected_by_id = {
        item.candidate_id: item.rejection_code.value
        for item in wallet.decisions
        if not item.accepted and item.rejection_code is not None
    }
    accepted_trades = tuple(item for item in isolated.trades if item.result_id in accepted_ids)
    observations = _merge_wallet_observations(
        isolated=isolated,
        missing_margin_ids=missing_margin_ids,
        rejected_by_id=rejected_by_id,
    )
    rejection_counter = Counter(dict(isolated.rejection_counts))
    rejection_counter.update(rejected_by_id.values())
    rejection_counter[_MISSING_MARGIN_CODE] += len(missing_margin_ids)
    campaign = HistoricalFuturesCampaignResult(
        campaign_id=isolated.campaign_id,
        starting_equity=isolated.starting_equity,
        ending_equity=wallet.ending_equity,
        observations=observations,
        trades=accepted_trades,
        split_metrics=isolated.split_metrics,
        rejection_counts=tuple(sorted(rejection_counter.items())),
    )
    return SharedHistoricalFuturesCampaignResult(
        campaign=campaign,
        wallet=wallet,
        wallet_config=wallet_config,
        configuration_hash=_hash_json(
            {
                "backtest": {
                    "fee_pct": request.backtest_config.fee_pct,
                    "slippage_pct": request.backtest_config.slippage_pct,
                    "maximum_holding_candles": request.backtest_config.maximum_holding_candles,
                    "conservative_intrabar": request.backtest_config.conservative_intrabar,
                },
                "wallet": wallet_config.to_payload(),
            }
        ),
    )


def write_shared_historical_futures_campaign(
    *,
    request: HistoricalFuturesCampaignRequest,
    result: SharedHistoricalFuturesCampaignResult,
) -> SharedHistoricalFuturesExecutionManifest:
    """Persist the shared result through the canonical writer and extend its manifest."""

    base_manifest = write_historical_futures_campaign(request=request, result=result.campaign)
    payload = result.to_payload()
    request.result_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result_hash = _hash_json(payload)
    base_manifest = HistoricalFuturesExecutionManifest(
        campaign_id=base_manifest.campaign_id,
        signal_records_hash=base_manifest.signal_records_hash,
        signal_configuration_hash=base_manifest.signal_configuration_hash,
        result_path=base_manifest.result_path,
        result_hash=result_hash,
        total_decisions=base_manifest.total_decisions,
        trade_count=base_manifest.trade_count,
        split_counts=base_manifest.split_counts,
    )
    manifest = SharedHistoricalFuturesExecutionManifest(
        base=base_manifest,
        wallet_configuration_hash=result.configuration_hash,
        wallet_rejection_counts=result.wallet.rejection_counts,
    )
    request.execution_manifest_path.write_text(
        json.dumps(manifest.to_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    reloaded = load_historical_futures_execution_manifest(request.execution_manifest_path)
    if reloaded.result_hash != result_hash:
        raise ValueError("shared historical futures manifest result hash mismatch")
    return manifest


def _required_margin_by_key(
    payloads: tuple[dict[str, object], ...],
) -> dict[tuple[str, str], float]:
    output: dict[tuple[str, str], float] = {}
    for payload in payloads:
        if not bool(payload.get("accepted", False)):
            continue
        decision_time = payload.get("decision_time")
        symbol = payload.get("symbol")
        analysis = payload.get("analysis")
        if not isinstance(decision_time, str) or not isinstance(symbol, str):
            continue
        if not isinstance(analysis, Mapping):
            continue
        position = analysis.get("position_size")
        if not isinstance(position, Mapping):
            continue
        margin = _first_positive_float(
            position,
            "required_margin",
            "margin_required",
            "margin",
        )
        if margin is not None:
            output[(decision_time, symbol)] = margin
    return output


def _merge_wallet_observations(
    *,
    isolated: HistoricalFuturesCampaignResult,
    missing_margin_ids: set[str],
    rejected_by_id: Mapping[str, str],
) -> tuple[HistoricalFuturesObservation, ...]:
    trade_by_key = {
        (item.trade.signal.generated_at.isoformat(), item.trade.signal.symbol): item
        for item in isolated.trades
    }
    output: list[HistoricalFuturesObservation] = []
    for observation in isolated.observations:
        item = trade_by_key.get((observation.decision_time, observation.symbol))
        if item is None or observation.status != "simulated":
            output.append(observation)
            continue
        code = None
        if item.result_id in missing_margin_ids:
            code = _MISSING_MARGIN_CODE
        elif item.result_id in rejected_by_id:
            code = rejected_by_id[item.result_id]
        if code is None:
            output.append(observation)
        else:
            output.append(
                HistoricalFuturesObservation(
                    symbol=observation.symbol,
                    split=observation.split,
                    decision_time=observation.decision_time,
                    status="wallet_rejected",
                    rejection_codes=(code,),
                    reason="shared-wallet account constraints rejected the plan",
                )
            )
    return tuple(output)


def _first_positive_float(value: Mapping[str, object], *keys: str) -> float | None:
    for key in keys:
        selected = value.get(key)
        if isinstance(selected, int | float):
            result = float(selected)
            if math.isfinite(result) and result > 0.0:
                return result
    return None


def _hash_json(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
