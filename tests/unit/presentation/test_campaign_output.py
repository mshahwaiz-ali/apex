from apex.presentation.backtest_output import render_campaign


def test_render_campaign_exposes_complete_research_sections() -> None:
    payload = {
        "months": ["2026-01", "2026-02"],
        "dataset_dir": "data/research/binance_um",
        "universe_path": "data/research/binance_um/universe_by_month.json",
        "universe_size": 30,
        "symbol_count": 2,
        "universe_by_month": {
            "2026-01": ["BTCUSDT", "ETHUSDT"],
            "2026-02": ["BTCUSDT"],
        },
        "verified_file_count": 4,
        "verified_files": {"a.zip": "abc", "b.zip": "def"},
        "missing_file_count": 1,
        "missing_files": {"2026-02:ETHUSDT:klines": "HTTPStatusError: unavailable"},
        "manifest": "data/research/binance_um/campaign_manifest.json",
        "manifest_hash": "1234567890abcdef",
        "manifest_schema_version": 1,
        "model_training": "not requested",
        "artifacts": {
            "dataset_dir": "data/research/binance_um",
            "universe": "data/research/binance_um/universe_by_month.json",
            "manifest": "data/research/binance_um/campaign_manifest.json",
        },
    }

    rendered = render_campaign(payload)

    for section in (
        "Campaign Configuration",
        "Dataset Coverage",
        "Universe Summary",
        "Missing Data",
        "Manifest",
        "Model Training",
        "Artifacts",
    ):
        assert section in rendered
    assert "COMPLETE WITH MISSING DATA" in rendered
    assert "2026-02:ETHUSDT:klines" in rendered
    assert "No profitability claim" in rendered


def test_render_campaign_reports_complete_coverage_without_missing_records() -> None:
    rendered = render_campaign(
        {
            "months": ["2026-01"],
            "verified_file_count": 3,
            "verified_files": {"a": "1", "b": "2", "c": "3"},
            "missing_file_count": 0,
            "missing_files": {},
            "universe_by_month": {"2026-01": ["BTCUSDT"]},
            "model_training": {"status": "completed", "artifact_count": 3},
        }
    )

    assert "▶  COMPLETE" in rendered
    assert "No missing campaign files." in rendered
    assert "completed" in rendered
