"""CLI for deterministic historical spot dataset acquisition."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from apex.application.spot_historical_dataset import (
    acquire_spot_historical_dataset,
    write_spot_historical_dataset,
)
from apex.data.providers import BinanceHistoricalRangeMarketDataProvider
from apex.data.providers.errors import MarketDataProviderError


def register_spot_historical_dataset_commands(dataset_app: typer.Typer) -> None:
    @dataset_app.command("spot-history-fetch")
    def spot_history_fetch(
        dataset_id: Annotated[str, typer.Option("--dataset-id")],
        symbols: Annotated[str, typer.Option("--symbols")],
        timeframes: Annotated[str, typer.Option("--timeframes")] = "4h",
        start: Annotated[str, typer.Option("--start")] = "",
        end: Annotated[str, typer.Option("--end")] = "",
        records_output: Annotated[
            Path,
            typer.Option("--records-output", dir_okay=False),
        ] = Path("data/spot/history.jsonl"),
        manifest_output: Annotated[
            Path,
            typer.Option("--manifest-output", dir_okay=False),
        ] = Path("data/spot/history.manifest.json"),
        force: Annotated[bool, typer.Option("--force")] = False,
    ) -> None:
        """Fetch one immutable multi-symbol historical spot dataset."""

        try:
            start_time = _parse_time(start, "start")
            end_time = _parse_time(end, "end")
            requested_symbols = _parse_csv(symbols, "symbols")
            requested_timeframes = _parse_csv(timeframes, "timeframes")
            with BinanceHistoricalRangeMarketDataProvider() as provider:
                result = acquire_spot_historical_dataset(
                    dataset_id=dataset_id,
                    provider=provider,
                    symbols=requested_symbols,
                    timeframes=requested_timeframes,
                    start_time=start_time,
                    end_time=end_time,
                )
            write_spot_historical_dataset(
                result=result,
                records_path=records_output,
                manifest_path=manifest_output,
                force=force,
            )
        except (FileExistsError, MarketDataProviderError, OSError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "SPOT_HISTORICAL_DATASET_COMPLETED "
            f"| dataset_id={result.manifest.dataset_id} "
            f"| candles={result.manifest.candle_count} "
            f"| dataset_hash={result.manifest.dataset_sha256} "
            f"| records={records_output} "
            f"| manifest={manifest_output}"
        )


def _parse_csv(value: str, label: str) -> tuple[str, ...]:
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    if not items:
        raise ValueError(f"historical spot {label} cannot be empty")
    if len(set(items)) != len(items):
        raise ValueError(f"historical spot {label} cannot contain duplicates")
    return items


def _parse_time(value: str, label: str) -> datetime:
    if not value.strip():
        raise ValueError(f"historical spot {label} time is required")
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
