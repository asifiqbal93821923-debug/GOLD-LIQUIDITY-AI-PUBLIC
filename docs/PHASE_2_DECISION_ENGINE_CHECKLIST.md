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

## Remaining before Phase 2 can be called trading-validated

- [ ] Compare 1H direction and plan against actual TradingView reference fixtures from the user's exact symbol/feed, Pine version and inputs.
- [ ] Calibrate the 1H structural/ATR entry, SL and TP proposal on historical data.
- [ ] Run walk-forward and out-of-sample tests with realistic spread, slippage and commission.
- [ ] Paper-trade forward test before any real-money use.

## Verification boundary

The software implementation and current automated regression/CI checks are complete. Trading validation is not complete. The TradingView parity fixture guide is in `docs/PHASE_2_TRADINGVIEW_FIXTURE_GUIDE.md`; an actual export is required and has not yet been supplied. Current Alpha/SMC modules are adapters, not parity-certified full Pine ports. Public sampled XAU data is not broker Bid/Ask or true traded volume. No institutional order book/MBO or true CVD feed is connected. The application does not place orders. Passing software tests does not establish profitability.
