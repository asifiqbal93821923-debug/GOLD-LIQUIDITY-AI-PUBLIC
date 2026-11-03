# Phase 2 — 1H Primary Decision Engine

Started: 2026-11-03

## Decision hierarchy

- 1H is the sole source of primary BUY/SELL direction and the initial entry/SL/TP plan.
- 4H is macro context: confirmed opposition vetoes; neutral context does not replace 1H.
- 15M must provide a confirmed, aligned setup.
- 5M is optional entry refinement only. Missing or unconfirmed 5M data does not block a valid higher-timeframe setup; a confirmed opposing 5M trigger vetoes immediate entry.
- Incomplete/stale data, unacceptable spread, ambiguous structure, invalid plan or missing required timeframe evidence returns WAIT.

## Implemented and verified in this phase

- [x] Hardened the unified decision gate to require a plan explicitly sourced from 1H.
- [x] Added finite, positive numeric validation for entry, stop and all three targets.
- [x] Added directional risk-order validation: BUY = SL < entry < TP1 < TP2 < TP3; SELL = SL > entry > TP1 > TP2 > TP3.
- [x] Kept 5M optional; only a confirmed opposite 5M trigger can veto.
- [x] Added regression tests for optional 5M, missing 4H/15M evidence, non-1H plan source, NaN/boolean/zero levels and risk safety.
- [x] Added MTF closed-candle/no-lookahead edge-case tests: 4H closed-bar selection, 5M forming-bar cutoff and exact close-boundary behavior.
- [x] Fixed the stale closed-bar test fixture and reran CI successfully.
- [x] Latest GitHub Actions on commit `400f12b782472058f645c27027e50dbdd1ce1d65`: backend tests, frontend build/syntax and Docker build all completed successfully.

## Historical-data validation attempt (2026-11-03)

- [x] Inspected the currently committed free XAUS sampled snapshot and collector configuration.
- [x] Confirmed the public feed is sampled indicative spot data at roughly 5-minute intervals, with an upstream maximum history of 48 hours; it is not broker Bid/Ask or traded OHLCV.
- [x] Calculated the theoretical maximum from 48 hours: 12 x 4H bars, 48 x 1H bars and 192 x 15M bars (before missing samples). The MTF replay requires at least 50 fully closed bars in each of 4H, 1H and 15M.
- [x] Confirmed the current available history therefore cannot satisfy the MTF backtest minimum. No genuine historical MTF performance, calibration or walk-forward result can be calculated from this dataset.
- [ ] Obtain at least 100 closed bars per timeframe from the same XAUUSD TradingView/broker feed (more history preferred), including exact Pine script version and inputs.
- [ ] Compare 1H direction and plan against actual TradingView reference fixtures.
- [ ] Calibrate the 1H structural/ATR entry, SL and TP proposal on genuine historical OHLC data.
- [ ] Run walk-forward and out-of-sample tests with realistic spread, slippage and commission.
- [ ] Paper-trade forward test before any real-money use.

## Verification boundary

Software implementation and automated CI/regression checks are complete. MTF alignment/no-lookahead behavior is covered by unit tests, but the strategy has not been validated on sufficient real historical market data. TradingView parity cannot be verified without an actual export from the user's exact chart/feed and Pine inputs. Current Alpha/SMC modules are adapters, not parity-certified full Pine ports. Public sampled XAU data is not broker Bid/Ask or true traded volume. No institutional order book/MBO or true CVD feed is connected. The application does not place orders. Passing software tests does not establish profitability.


## Trading validation tooling update (2026-11-03)

- [x] Added `scripts/compare_tradingview_signals.py` for timestamp-aligned BUY/SELL/WAIT event comparison and mismatch reporting.
- [x] Added `scripts/walk_forward_validation.py` for chronological fixed-parameter train/holdout replay with both partitions required to meet the MTF engine's minimum closed-bar history.
- [x] Added `scripts/paper_trade_ledger.py` for offline hypothetical trade logging, entry-zone checks, spread/slippage assumptions and conservative OHLC stop/target resolution. It never sends broker orders.
- [x] Added unit tests for parity mismatch reporting, insufficient walk-forward history and paper-ledger WAIT/entry behavior. Backend test workflow passed 64 tests on commit `f6c18bfbade91008d276b62698f026d40dfab409`.
- [x] Added operator guide at `docs/TRADING_VALIDATION_TOOLS.md`.
- [ ] Actual TradingView parity remains blocked pending the user's same-feed signal export and Pine version/inputs.
- [ ] Actual historical calibration and walk-forward metrics remain blocked pending sufficient genuine broker/TradingView 4H/1H/15M OHLC history and target-broker cost assumptions.
- [ ] Paper-trading observation period has not started/completed. The ledger must be fed continuously with new closed candles and realistic quote costs.

**Important:** Validation infrastructure is implemented and tested; market-data-dependent validation results are not complete. Do not report strategy profitability or exact Pine parity from unit tests.

## Research implementation update (2026-11-03)

- [x] Added `scripts/prepare_xauusd_dataset.py`: imports TradingView OHLC CSVs only when the operator supplies one exact source + ticker for every timeframe; validates UTC timestamps, candle closure, OHLC integrity, duplicates and history sufficiency. Source labels are operator assertions and still require visual verification against the TradingView chart header.
- [x] Made the 1H structure/ATR Entry, SL and three RR target parameters configurable in the causal MTF replay.
- [x] Added `scripts/calibrate_trade_plan.py`: 60/20/20 chronological train/validation/sealed-test calibration; spread, slippage and commission passed into each replay; only train/validation select the candidate and the sealed test is evaluated once.
- [x] Added `scripts/analyze_price_action_setups.py`: separate causal OHLC classifications for liquidity-sweep, false-breakout and confirmed retest, with descriptive forward MFE/MAE/close-return summaries.
- [x] Increased the MTF replay's 1H history ceiling to 6,000 candles for longer chronological samples.
- [x] Added regression tests for sweep/false-breakout, retest confirmation, incomplete forward outcomes, and invalid/unclosed CSV rows.

## What is still not complete (data-dependent)

- [ ] **Same-feed history is not yet collected.** The new importer is ready, but no historical TradingView export is currently available in this repository. The earlier 48-hour sampled public dataset is not enough. Do not substitute Dukascopy or another provider and label it as the user's TradingView feed.
- [ ] **Actual Pine/Python parity is not run.** Exact TradingView ticker/provider, full Pine source/version, input values, and exported plotted BUY/SELL/WAIT events are not present. TradingView's CSV export can include OHLC and script plots when those values are plotted by the script.
- [ ] **Historical 1H calibration has no empirical winner yet.** The 48-candidate calibration harness is implemented; it must be run on the same-feed closed OHLC set with the target broker's real spread, slippage and commission assumptions.
- [ ] **False-breakout/sweep/retest have code-level classifications, not market-performance validation.** Their frequency and forward outcomes still need to be measured on the same-feed historical 15M data. They are OHLC proxies, not order-book/MBO observations.
- [ ] **Walk-forward/OOS report is not yet produced on real data.** The runner and explicit transaction-cost model exist; no defensible result is available until same-feed data and broker costs are supplied.
- [ ] **Optimizer sealed-test result is pending.** Candidate generation/selection logic exists, but no candidate is selected or tested without the full chronological dataset. Never re-optimize against the sealed test.
- [ ] **Continuous forward paper-trading period has not started or completed.** The offline ledger exists, but continuous observation requires a running feed/receiver, persistent ledger storage and elapsed market sessions. No broker orders are sent.

**Phase 2 acceptance rule:** software tools and tests being present is not equivalent to historical evidence. Keep Phase 2 open until the same-feed dataset, Pine parity report, calibrated trade-plan report, costed walk-forward/OOS report, sealed-test report and a pre-defined forward paper-trading sample have all been saved and reviewed.
