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
- [ ] Calibrate 1H entry width, ATR period/buffer, swing lookback and TP R multiples using training data only.
- [ ] Separate signal generation from calibration/optimizer logic.
- [ ] Report trade frequency, skipped entries, false positives, expectancy, average R, profit factor, max drawdown and sample size.
- [ ] Do not optimize on win rate alone; prevent test-set leakage.

### P2.4 — Out-of-sample and walk-forward
- [ ] Freeze a chronological untouched holdout period before tuning.
- [ ] Implement rolling/anchored walk-forward folds with training and test boundaries recorded.
- [ ] Run each fold with costs and settings fixed before its test segment.
- [ ] Report fold-level and aggregate results, including losing/zero-trade folds.
- [ ] Verify no trade from a training interval is counted as out-of-sample.

### P2.5 — Realistic execution-cost scenarios
- [ ] Calibrate point size, spread, slippage and commission from the intended broker's actual contract specification and observed quotes.
- [ ] Sweep conservative/base/adverse cost scenarios and session/rollover conditions.
- [ ] Keep spread gate closed until a defensible maximum spread is configured.
- [ ] Explain that candle OHLC cannot resolve true intrabar execution order; retain conservative assumptions.

### P2.6 — Forward/paper validation and release gate
- [ ] Run a logged paper-forward period after historical gates pass.
- [ ] Compare live decisions with subsequent closed candles; record missed/duplicate/invalidated signals.
- [ ] Require stable data, no look-ahead, acceptable OOS robustness and documented risk before any later release decision.
- [ ] No broker order execution in Phase 2.

## Known blockers / external dependencies
- No confirmed live MT5 broker feed is currently connected; user has no desktop PC for MetaTrader Desktop testing.
- Historical store previously returned zero 1H candles in the production API. The public indicative sampled-price archive is not broker OHLCV and must not be converted into synthetic candles. The repository still has no verified same-feed 4H/1H/15M CSV dataset.
- No TradingView golden fixture package or complete exact Pine source/settings package for PRO XAU V2.0 and Advanced SMC MTF Pro is currently present in the repository; parity execution is blocked until those exports are added.
- Actual broker spread/commission/slippage contract details have not been calibrated.
- OHLCV footprint values are proxies, not real MBO/order-book, true aggressor CVD, open interest or iceberg data.

## Acceptance rule
A feature marked implemented is not marked validated until its stated data/test evidence exists. Synthetic unit fixtures are for software correctness only and must never be presented as historical market-performance evidence.