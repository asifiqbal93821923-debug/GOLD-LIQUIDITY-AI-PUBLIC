# Phase 2 — Strategy Engine & Historical Validation

Last audited: 2026-11-03
Baseline commit: 0560e789e82c48771a3e40932d07f31f9d37f795

## Goal
Turn the existing 4H/1H/15M/optional-5M analysis foundation into a reproducible, historically tested XAUUSD research system. Phase 2 does not enable broker order execution and does not imply profitability.

## Existing implementation (code present; validation still required)
- [x] 4H macro context and veto; 1H primary direction and trade-plan source; 15M setup; optional 5M trigger refinement.
- [x] Closed-candle decision checks and WAIT vetoes for missing/stale/incomplete data, opposing macro/setup, ambiguous structure/sweep, invalid 1H risk plan and unacceptable spread.
- [x] Initial Python adapters: Alpha Signal, SMC structure, WSB, AI Channels and OHLCV institutional-footprint proxies.
- [x] Gold Report orchestration and POST /api/analysis/gold-report.
- [x] Initial 1H entry/SL/TP1/TP2/TP3 proposal (uncalibrated).
- [x] 1H Alpha replay and causal 4H/1H/15M/optional-5M replay endpoint.
- [x] Next-bar execution, entry-zone validation, partial target exits, conservative stop-first handling, and configurable spread/slippage/commission assumptions.
- [x] MTF replay filters forming/future bars and uses only higher/lower timeframe bars fully closed by each 1H decision close.
- [x] Unit tests cover key decision vetoes, optional 5M behavior, cost application, stop-first handling and MTF close-time alignment.

## Phase 2 work packages

### P2.1 — Data and replay correctness
- [x] Same-feed TradingView CSV import/preparation pipeline exists (`scripts/prepare_xauusd_dataset.py`); it rejects naive local timestamps and forming/future bars, checks duplicate timestamps, records provenance, and requires minimum history for chronological partitions.
- [x] Historical candle audit API added at `POST /api/market/history/audit`; reports coverage, closed/forming/future rows, duplicates, out-of-order rows, malformed OHLCV and gaps without synthesizing candles.
- [x] Deterministic tests cover duplicate/out-of-order rows, gaps, invalid OHLC, closed/forming/future classification, and exact MTF close-boundary behavior.
- [x] Replay code and tests enforce fully closed 4H/1H/15M/optional-5M bars at each 1H decision close.
- [ ] Import a sufficiently deep, timestamped XAUUSD OHLC dataset from one verified provider/feed for 4H, 1H and 15M; 5M is optional.
- [ ] Verify chart ticker/provider, timezone, broker contract/point size and volume semantics against source documentation.
- [ ] Run the quality audit against the real imported dataset and review session/weekend gaps before replay.

### P2.2 — Pine reference parity
- [ ] Export TradingView golden fixtures from the exact supplied Pine versions and settings.
- [ ] Compare Alpha, SMC, WSB and AI Channels outputs candle-by-candle.
- [ ] Fix and document mismatches; keep source-parity and corrected variants distinct.
- [ ] Do not claim parity until fixture comparisons pass.

### P2.3 — Trade-plan calibration
- [x] Dedicated 1H calibration runner exists (`scripts/calibrate_trade_plan.py`) with 48 deterministic ATR/structure/entry-width/TP-R candidates; selection uses train + validation only and touches the sealed test once.
- [x] Calibration is separate from signal generation and uses the causal MTF replay; spread, slippage, commission and point-size assumptions are explicit.
- [x] Calibration report now includes trade count, skipped signals/rate, losing trades, expectancy in R, average R, profit factor, net PnL, max drawdown, sample-size warning, chronological bar counts and split boundaries.
- [x] Unit test added for the new calibration diagnostics.
- [ ] Run the calibration against verified same-feed 4H/1H/15M OHLCV and broker-verified execution costs; inspect the generated report.
- [ ] Confirm the sealed test is not used to choose or revise parameters; evaluate minimum sample size and robustness across regimes.
- [ ] Report false positives/trade frequency separately with the price-action setup diagnostic and reconcile definitions before any final acceptance.
- [ ] Do not optimize on win rate alone; prevent test-set leakage.

### P2.4 — Out-of-sample and walk-forward
- [ ] Freeze a final chronological untouched holdout period before any tuning; this remains an empirical acceptance gate.
- [x] Implement rolling/anchored walk-forward folds with explicit training and disjoint test boundaries (`scripts/rolling_walk_forward_validation.py`).
- [x] Pass fixed execution costs/settings unchanged to each fold; no fold test is used to select parameters.
- [x] Report fold-level metrics, zero/losing folds, aggregate OOS trade count/PnL and leakage-control assertions.
- [x] Unit tests cover short-history refusal and invalid fold configurations.
- [ ] Execute all folds and inspect reports on verified same-feed candles with XM360-verified costs; confirm training/test separation from the produced artifact.

### P2.5 — Realistic execution-cost scenarios
- [x] Add reproducible base/conservative/adverse execution-cost scenarios using the same causal MTF replay (scripts/execution_cost_scenarios.py).
- [x] Validate finite/non-negative cost inputs, positive point size, stress-scenario ordering and fail-closed spread-limit behavior with unit tests.
- [x] Enforce the P2.5 spread gate in the actual MTF decision path: no positive maximum spread means WAIT; an observed spread above the configured cap means WAIT.
- [x] Emit scenario metrics, explicit cost assumptions, provenance status and OHLC/intrabar execution limitations.
- [x] Add a timestamped bid/ask quote analyzer for UTC session and user-configured rollover distributions (scripts/analyze_broker_quotes.py); reject naive timestamps, invalid/duplicate quotes and insufficient total sample size.
- [x] Add unit tests for quote parsing, spread statistics, rollover bucketing and provenance disclaimers.
- [x] Wire optional XM360 quote-audit execution and spread-cap inputs into the Phase 2 research workflow.
- [ ] Review XM360's actual XAUUSD contract specification: exact symbol, point/tick size, contract size, account-type commission and trading schedule.
- [ ] Supply and manually verify timestamped XM360 bid/ask observations; quote-tool output alone does not authenticate the broker source.
- [ ] Calibrate actual slippage and commission from broker execution/fill evidence; bid/ask quotes alone do not establish either.
- [ ] Run all three scenarios on verified same-feed history with verified XM360 costs; inspect trade count, net PnL, average R, profit factor and drawdown.
- [ ] Validate each session and the documented rollover window with adequate observed quote samples; UTC buckets are diagnostic and not DST-adjusted market-session definitions.
- [ ] Set a defensible maximum spread from reviewed observations; keep the P2.5 spread gate closed until then.
- [x] Retain conservative stop-first handling; candle OHLC cannot resolve true intrabar execution order.

P2.5 implementation status: code and unit-test scope implemented; broker-specific empirical acceptance remains pending until the evidence above is reviewed.

### P2.6 — Forward/paper validation and release gate
- [ ] Run a logged paper-forward period after historical gates pass.
- [ ] Compare live decisions with subsequent closed candles; record missed/duplicate/invalidated signals.
- [ ] Require stable data, no look-ahead, acceptable OOS robustness and documented risk before any later release decision.
- [ ] No broker order execution in Phase 2.

## Known blockers / external dependencies
- No confirmed live MT5 broker feed is currently connected; user has no desktop PC for MetaTrader Desktop testing.
- Historical store previously returned zero 1H candles in the production API. The public indicative sampled-price archive is not broker OHLCV and must not be converted into synthetic candles. The repository still has no verified same-feed 4H/1H/15M CSV dataset.
- No TradingView golden fixture package or complete exact Pine source/settings package for PRO XAU V2.0 and Advanced SMC MTF Pro is currently present in the repository; parity execution is blocked until those exports are added.
- Actual XM360 spread/commission/slippage and contract point-size details have not been calibrated.
- OHLCV footprint values are proxies, not real MBO/order-book, true aggressor CVD, open interest or iceberg data.

## Acceptance rule
A feature marked implemented is not marked validated until its stated data/test evidence exists. Synthetic unit fixtures are for software correctness only and must never be presented as historical market-performance evidence.
