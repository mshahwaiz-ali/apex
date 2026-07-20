import json
from pathlib import Path

from apex.cli_commands import research


def test_campaign_payload_preserves_coverage_and_artifact_details(
    monkeypatch,
    tmp_path: Path,
) -> None:
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    universe_path = dataset_dir / "universe_by_month.json"
    universe_path.write_text(
        json.dumps(
            {
                "2026-01": ["BTCUSDT", "ETHUSDT"],
                "2026-02": ["BTCUSDT"],
            }
        )
    )
    monkeypatch.setattr(
        research,
        "latest_complete_utc_months",
        lambda now, count: ("2026-01", "2026-02"),
    )

    payload = research._run_public_data_campaign(
        dataset_dir=dataset_dir,
        symbols_file=universe_path,
        start=None,
        end=None,
        download_missing=False,
        train_model=False,
    )

    assert payload["date_range"] == {"start": "2026-01", "end": "2026-02"}
    assert payload["symbol_count"] == 2
    assert payload["symbols"] == ["BTCUSDT", "ETHUSDT"]
    assert payload["universe_by_month"]["2026-01"] == ["BTCUSDT", "ETHUSDT"]
    assert payload["verified_files"] == {}
    assert payload["missing_files"] == {}
    assert payload["artifacts"]["universe"] == str(universe_path)
    assert payload["calibration_authoritative"] is False
    assert Path(payload["manifest"]).exists()
