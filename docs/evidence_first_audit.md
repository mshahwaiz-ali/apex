# Apex Evidence-First Runtime Audit

This audit anchors the trading-engine roadmap to the current runtime modules. It is intentionally evidence-first: zero trades are valid when the engine cannot prove a setup, and diagnostics must explain the rejection before any filter calibration is considered.

| Area | Runtime Authority | Config | Evidence Added | Remaining Calibration Gap |
| --- | --- | --- | --- | --- |
| Universe | `apex.application.futures_scan_selection` | `futures_screener.quote_asset`, allowlist, blacklist | hard-eligible counts and exclusions | exchange metadata drift monitoring |
| Screening | `apex.application.futures_screening` | `futures_screener.*` | longer candle surveillance and dynamic lane budgets | broader multi-symbol walk-forward validation |
| Market Environment | `apex.market_environment` | `market_environment.*`, timeframe roles | role labels already serialized per timeframe | role-gated authority should replace any residual vote-like interpretation |
| Strategies | `apex.strategies` | `strategy_routing.enabled` | candidate counts, rejection codes, near-miss states, canonical family counts | collapse legacy strategy IDs into subtype/modifier semantics over time |
| Entry | `apex.strategies.entry` | `EntrySelectionConfig` | target-room and risk-aware chase ceilings | calibrate fill quality and non-fill cost by family |
| Stops | `apex.application.discovery_setup` and `apex.application.trade_geometry` | structural buffer constants | family-aware stop evidence in public setup payloads | independent stop-quality model by strategy family |
| Targets | `apex.application.trade_geometry` | strategy target generation | target context, R, source, conditionality, reachability hint | empirical partial/runner policy per family |
| Scoring | `apex.scoring` | scoring configuration | zero-trade ranking/rejection distributions | calibrated statistics must remain separate from quality score |
| Backtesting | `apex.cli_commands.backtesting` | backtest CLI options | per-decision calibration records with future replay outcomes | dataset-level multi-symbol campaigns and untouched holdout periods |
| Presentation | `apex.application.enriched_public_output` | CLI output mode | machine-readable no-trade diagnostics | concise operator summaries for the new diagnostics |

Implementation rule: entry filters stay strict. Diagnostics may identify missed or developing setups, but they must not authorize execution by themselves.
