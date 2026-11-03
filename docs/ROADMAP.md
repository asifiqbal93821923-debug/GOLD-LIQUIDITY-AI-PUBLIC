# Development Roadmap

## Phase 1 — Market data foundation
- [ ] Confirm the execution reference feed (preferred: user's MT5 broker feed via a server-side bridge).
- [ ] Implement provider adapter interface; keep API credentials server-side.
- [ ] Validate XAUUSD symbol mapping, timezone, session gaps, candle boundaries and volume semantics.
- [ ] Load historical candles and stream live updates without fabricating data.

## Phase 2 — Pine parity and engine registry
- [x] Receive Alpha Signal Engine Pro source; create initial Python port, API contract and basic tests.
- [x] Receive complete LuxAlgo Smart Money Concepts source and complete source-level audit.
- [x] Receive complete Wick Sequence Breakout (WSB) source; document logic, license and caveats.
- [x] Receive complete LuxAlgo AI Channels (Clustering) source; document algorithm, license and caveats.
- [x] Create unified engine feature-selection and architecture blueprint.
- [x] Add initial WAIT-first confluence decision gate and API contract.
- [ ] Port selected features from Alpha, SMC, WSB and AI Channels into isolated engine modules; do not merge source code into one monolith.
- [x] Add first OHLCV-based institutional liquidity/footprint proxy module and Gold Report AI API contract.
- [ ] Add licensed live order-book/MBO and trade-print provider adapter; current order-book fields remain unavailable.
- [ ] Implement true order-level iceberg, aggressor-side CVD, open-interest and large-print feeds.
- [ ] Build TradingView-exported golden OHLCV fixtures and certify parity per engine.
- [ ] Fix SMC MTF lookahead/repainting risk, array-removal behavior and unbounded history retention in corrected mode.
- [ ] Integrate calculated engine outputs with correlated-feature controls and confidence calibration.

## Phase 3 — Chart and market structure
- [ ] Render real OHLC candles on the chart for 5m, 15m, 30m, 1h, 4h and 1D.
- [ ] Make 1H the primary analysis timeframe; 4H macro confirmation; 15m setup; 5m execution confirmation.
- [ ] Keep 1H/4H zones fixed when viewing 3m/5m charts; map by timestamps and price, not chart-local pivots.
- [ ] Add confirmed swing structure, BOS/CHoCH, support/resistance and candle-derived supply/demand.
- [ ] Add EQH/EQL, confirmed FVG, prior D/W/M levels and liquidity sweep estimates.
- [ ] Keep all meaningful markings on the main candlestick chart; no separate lower pane.

## Phase 4 — Trade planning and validation
- [x] Add initial WAIT-first confluence gate that rejects missing, unconfirmed or conflicting evidence (not yet connected to calculated indicator engines).
- [ ] Add entry trigger, invalidation, SL, TP1/TP2/TP3 and R-multiple planner.
- [ ] Add spread, commission, slippage and session sensitivity to reports.
- [ ] Run historical replay, backtests, walk-forward tests and anti-repainting checks.
- [ ] Validate signal frequency and false-positive rate; never optimize only for win rate.

## Phase 5 — Web and Android delivery
- [ ] Connect a production market data provider and live candle stream.
- [x] Add POST /api/analysis/institutional-footprint and POST /api/analysis/gold-report endpoints (proxy/contract only; not live feed).
- [ ] Responsive Bengali dashboard with trend, structure, liquidity, setup and risk explanations.
- [ ] PWA installation and offline-safe shell (market data remains online).
- [ ] Android packaging only after web core, feed and validation are stable.
- [ ] Deployment, monitoring, secret management and operational documentation.

## Current verified state
- [x] React + Vite frontend foundation and build workflow.
- [x] FastAPI backend foundation.
- [x] Alpha Signal Engine initial port, endpoint and basic tests.
- [x] Four indicator families received and reviewed at source/intake level.
- [x] Complete SMC source-level audit recorded; not yet ported or parity-certified.
- [x] Unified architecture and WAIT-first decision concept documented.
- [ ] No production market feed, certified Pine parity, fully calculated trade planner, live MBO/CVD/OI feed, or Android package yet.
- [ ] CI for the latest combined changes must be checked before claiming a green build.
