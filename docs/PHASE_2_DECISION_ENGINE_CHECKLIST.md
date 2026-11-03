# Phase 2 — 1H Primary Decision Engine

Started: 2026-11-03

## Decision hierarchy

- 1H is the sole source of primary BUY/SELL direction and the initial entry/SL/TP plan.
- 4H is macro context: confirmed opposition vetoes; neutral context does not replace 1H.
- 15M must provide a confirmed, aligned setup.
- 5M is optional entry refinement only. Missing or unconfirmed 5M data does not block a valid higher-timeframe setup; a confirmed opposing 5M trigger vetoes immediate entry.
- Incomplete/stale data, unacceptable spread, ambiguous structure, invalid plan or missing required timeframe evidence returns WAIT.

## Implemented in this phase

- [x] Hardened the unified decision gate to require a plan explicitly sourced from 1H.
- [x] Added finite, positive numeric validation for entry, stop and all three targets.
- [x] Added directional risk-order validation: BUY = SL < entry < TP1 < TP2 < TP3; SELL = SL > entry > TP1 > TP2 > TP3.
- [x] Kept 5M optional; only a confirmed opposite 5M trigger can veto.
- [x] Added regression tests for optional 5M, missing 4H/15M evidence, non-1H plan source, NaN/boolean/zero levels and risk safety.

## Not yet complete

- [ ] Confirm latest GitHub Actions backend, frontend and Docker workflows are green.
- [ ] Validate 1H direction against exported TradingView reference fixtures.
- [ ] Validate MTF closed-candle alignment and no-lookahead edge cases.
- [ ] Calibrate the 1H structural/ATR entry, SL and TP proposal on historical data.
- [ ] Run walk-forward and out-of-sample tests with realistic spread, slippage and commission.
- [ ] Paper-trade forward test before any real-money use.

## Verification boundary

Passing software tests only verifies implementation behavior, not trading profitability. Current Alpha/SMC modules are adapters, not parity-certified full Pine ports. Public sampled XAU data is not broker Bid/Ask or true traded volume. No institutional order book/MBO or true CVD feed is connected. The application does not place orders.
