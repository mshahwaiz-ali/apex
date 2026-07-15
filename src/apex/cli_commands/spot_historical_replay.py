"""CLI for leakage-safe historical spot signal replay."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from apex.application.spot_historical_replay import (
    replay_spot_historical_dataset,
    write_spot_historical_replay,
)
from apex.application.spot_live import load_spot_live_account
from apex.config.spot import load_spot_product_config
from apex.config.spot_strategies import load_spot_strategy_config


def register_spot_historical_replay_commands(dataset_app: typer.Typer) -> None:
    @dataset_app.command("spot-history-replay")
    def spot_history_replay(
        campaign_id: Annotated[str, typer.Option("--campaign-id")],
        dataset_records: Annotated[
            Path,
            typer.Option("--dataset-records", exists=True, dir_okay=False, readable=True),
        ],
        dataset_manifest: Annotated[
            Path,
            typer.Option("--dataset-manifest", exists=True, dir_okay=False, readable=True),
        ],
        account_file: Annotated[
            Path,
            typer.Option("--account", exists=True, dir_okay=False, readable=True),
        ],
        spot_config: Annotated[
            Path,
            typer.Option("--spot-config", exists=True, dir_okay=False, readable=True),
        ] = Path("config/spot.yaml"),
        strategy_config: Annotated[
            Path,
            typer.Option("--strategy-config", exists=True, dir_okay=False, readable=True),
        ] = Path("config/spot_strategies.yaml"),
        records_output: Annotated[
            Path,
            typer.Option("--records-output", dir_okay=False),
        ] = Path("data/spot/replay.jsonl"),
        manifest_output: Annotated[
            Path,
            typer.Option("--manifest-output", dir_okay=False),
        ] = Path("data/spot/replay.manifest.json"),
        warmup_candles_4h: Annotated[
            int,
            typer.Option("--warmup-candles-4h", min=180),
        ] = 180,
        force: Annotated[bool, typer.Option("--force")] = False,
    ) -> None:
        """Replay a verified historical spot dataset without future leakage."""

        try:
            account = load_spot_live_account(account_file).account
            result = replay_spot_historical_dataset(
                campaign_id=campaign_id,
                dataset_records_path=dataset_records,
                dataset_manifest_path=dataset_manifest,
                account=account,
                product_config=load_spot_product_config(spot_config),
                strategy_config=load_spot_strategy_config(strategy_config),
                warmup_candles_4h=warmup_candles_4h,
            )
            write_spot_historical_replay(
                result=result,
                records_path=records_output,
                manifest_path=manifest_output,
                force=force,
            )
        except (FileExistsError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "SPOT_HISTORICAL_REPLAY_COMPLETED "
            f"| campaign_id={result.manifest.campaign_id} "
            f"| decisions={result.manifest.decision_count} "
            f"| plans={result.manifest.accepted_plan_count} "
            f"| eligibility_passes={result.manifest.eligibility_pass_count} "
            f"| failures={result.manifest.failure_count} "
            f"| records_hash={result.manifest.records_sha256} "
            f"| records={records_output} "
            f"| manifest={manifest_output}"
        )
