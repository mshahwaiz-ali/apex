# Apex External Source Register

**Access date:** 2026-07-27

| Source | Claim used | Application | Limitation |
|---|---|---|---|
| Binance USD-M Futures REST API, https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data | Exchange metadata supplies trading rules; klines have exchange timestamps; funding, OI, and taker flow are separate series | Snapshot semantics, precision, dataset lineage | Some history endpoints have short retention; use verified archives |
| Binance Public Data repository and archive, https://github.com/binance/binance-public-data | Checksum-addressed monthly and daily futures archives, naming, and checksum convention | Funding, aggregate trade, mark/index/premium, and daily metrics ingestion | Archive presence does not prove a market was tradeable without point-in-time eligibility metadata |
| Bailey and Lopez de Prado, *The Deflated Sharpe Ratio*, https://ssrn.com/abstract=2460551 | Multiple testing and non-normal returns inflate reported Sharpe | Count tried configurations and withhold unsupported DSR/PBO claims | Does not supply strategy thresholds |
| Scikit-learn probability calibration guide, https://scikit-learn.org/stable/modules/calibration.html | Reliability diagrams and proper scores assess different probability qualities | Calibration reports and Brier decomposition | Calibration requires untouched labeled outcomes |
| Scikit-learn precision-recall guidance, https://scikit-learn.org/stable/auto_examples/model_selection/plot_precision_recall.html | Decision thresholds trade coverage/recall against precision | Abstention-frontier reporting | Higher precision alone does not establish positive expectancy |
| John J. Murphy local research | Structure, levels, confirmation, and structural objectives | Direction, invalidation, targets | Uploaded scan is incomplete |
| Steve Nison local research | Completed candle context, timing, and confluence | Contextual candle evidence | Patterns are not proven crypto edge or target generators |
| Mark Douglas local research | Predefined risk, uncertainty, consistency, and sample evaluation | Wording and evaluation discipline | Not a technical strategy source |

No online “best indicator setting” is accepted as a production value.
