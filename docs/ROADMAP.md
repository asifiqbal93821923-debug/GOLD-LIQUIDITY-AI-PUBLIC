# Development Roadmap

## Phase 1 — Market data foundation
- [ ] Confirm the execution reference feed (preferred: user's MT5 broker feed via a server-side bridge).
- [ ] Implement provider adapter interface; keep API credentials server-side.
- [ ] Validate XAUUSD symbol mapping, timezone, session gaps, candle boundaries and volume semantics.
- [ ] Load historical candles and stream live updates without fabricating data.

## Phase 2 — Pine parity and engine registry
- [x] Receive first Pine Script source and write a logic inventory (Alpha Signal Engine Pro).
- [x] Create initial Python port and API contract for Alpha Signal Engine.
- [x] Add deterministic contract tests and CI test step.
- [ ] Compare output with TradingView-exported OHLCV and identical settings; fix all material mismatches.
- [x] Receive LuxAlgo Smart Money Concepts source (partial) and document its candidate feature inventory.
- [ ] Receive the remaining LuxAlgo source and complete source audit.
- [x] Receive complete Wick Sequence Breakout (WSB) Pine v6 source and document logic, license and validation requirements.
- [x] Receive complete LuxAlgo AI Channels (Clustering) Pine v5 source and document algorithm, license and validation requirements.
- [x] Create unified engine feature-selection and architecture blueprint.
- [x] Add initial WAIT-first confluence decision gate and API contract.
- [ ] Port Alpha/WSB/AI Channels and complete SMC only after source audit; add parity fixtures.
- [ ] Build full confluence integration from actual calculated engine outputs, with correlated-feature controls.

## Phase 3 — Chart and market structure
- [ ] Render real OHLC candles on the chart for 1m, 5m, 15m, 30m, 1h, 4h and 1D.
- [ ] Add on-chart trend, momentum, regime and confirmed BUY/SELL/WAIT markers.
- [ ] Implement confirmed swing structure, BOS/CHOCH and support/resistance.
- [ ] Implement supply/demand zones with origin, freshness, mitigation and invalidation.
- [ ] Implement candle-derived liquidity sweep and displacement analysis; label it as an estimate, not actual order-book data.

## Phase 4 — Trade planning and validation
- [ ] Add entry trigger, invalidation, SL, TP1/TP2/TP3 and R-multiple planner.
- [x] Add initial WAIT-first confluence gate that rejects missing, unconfirmed or conflicting evidence (not yet connected to calculated indicator engines).
- [ ] Historical replay, backtesting, walk-forward testing and anti-repainting validation.
- [ ] Include spread, commission, slippage and session sensitivity in test reports.

## Phase 5 — Web and Android delivery
- [ ] Responsive web dashboard with Bengali plain-language explanations.
- [ ] PWA installation and offline-safe shell (market data remains online).
- [ ] Android packaging after web core and data feed are stable.
- [ ] Deployment, monitoring, secret management and operational documentation.

## Current verified state
- [x] React + Vite frontend foundation and build workflow.
- [x] FastAPI backend foundation.
- [x] Alpha Signal Engine initial port, endpoint and basic tests.
- [x] CORS now permits POST analysis routes.
- [x] Four engine families reviewed and documented; unified feature-selection blueprint committed.
- [x] Initial unified decision module, API endpoint and six unit tests committed; CI verification pending.
- [ ] No production market feed, Pine parity certification, complete chart analysis, calculated unified trade planner or Android package yet.
