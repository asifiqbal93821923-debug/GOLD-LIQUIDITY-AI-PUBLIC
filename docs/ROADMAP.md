# Development Roadmap

## Phase 1 — Market data foundation
- [x] Implement authenticated MT5 Expert Advisor bridge endpoint, EA source and setup guide.
- [ ] Configure the user's server token, install EA in MT5 desktop and verify fresh broker candles.
- [ ] Confirm the execution reference feed and broker symbol/session semantics.
- [x] Add a persistent SQLite historical-candle store and validated JSON import/retrieval API; keep secrets server-side. (Historical import only; provider adapter/live feed remains pending)
- [ ] Validate XAUUSD symbol mapping, timezone, session gaps, candle boundaries and volume semantics.
- [x] Load user-imported historical candles through API without fabricating data.
- [ ] Connect a licensed/provider historical source and stream live updates.

## Phase 2 — Pine parity and engine registry
- [x] Receive Alpha Signal Engine Pro source; create initial Python port, API contract and basic tests.
- [x] Receive complete LuxAlgo Smart Money Concepts source and complete source-level audit.
- [x] Receive complete Wick Sequence Breakout (WSB) source; document logic, license and caveats.
- [x] Receive complete LuxAlgo AI Channels (Clustering) source; document algorithm, license and caveats.
- [x] Create unified engine feature-selection and architecture blueprint.
- [x] Add initial WAIT-first confluence decision gate and API contract.
- [x] Upgrade decision gate to 4H macro / 1H primary trade plan / 15M setup / optional 5M entry refinement, with channel-conflict and ambiguous-liquidity vetoes.
- [x] Add isolated SMC, WSB and AI Channels OHLCV adapters (conservative first implementations; not full Pine ports or parity-certified).
- [x] Compose Alpha + SMC + WSB + AI Channels + liquidity proxy in Gold Report AI orchestration.
- [x] Add first OHLCV-based institutional liquidity/footprint proxy module and Gold Report AI API contract.
- [ ] Add licensed live order-book/MBO and trade-print provider adapter; current order-book fields remain unavailable.
- [ ] Implement true order-level iceberg, aggressor-side CVD, open-interest and large-print feeds.
- [ ] Build TradingView-exported golden OHLCV fixtures and certify parity per engine.
- [ ] Fix SMC MTF lookahead/repainting risk, array-removal behavior and unbounded history retention in corrected mode.
- [x] Integrate initial calculated engine outputs with conservative WAIT-first hierarchy and correlated context vetoes.
- [ ] Calibrate evidence weights and confidence only after walk-forward/out-of-sample testing.

## Phase 3 — Chart and market structure
- [x] Render imported historical OHLC candles on the chart for supported timeframes; live candles remain pending.
- [ ] Make 1H the primary analysis timeframe; 4H macro context/veto; 1H sole primary direction and trade-plan source; 15m setup confirmation; optional 5m entry refinement.
- [ ] Keep 1H/4H zones fixed when viewing 3m/5m charts; map by timestamps and price, not chart-local pivots.
- [x] Add initial 1H swing high/low, FVG, OB-candidate and EQH/EQL price-line overlays to the main chart (candidate levels; full zone rendering/validation pending).
- [ ] Add EQH/EQL, confirmed FVG, prior D/W/M levels and liquidity sweep estimates.
- [ ] Keep all meaningful markings on the main candlestick chart; no separate lower pane.

## Phase 4 — Trade planning and validation
- [x] Add initial WAIT-first confluence gate that rejects missing, unconfirmed or conflicting evidence (not yet connected to calculated indicator engines).
- [x] Add initial 1H structural/ATR entry zone, invalidation, SL and TP1/TP2/TP3 proposal (not calibrated or backtest-validated).
- [x] Add MT5 Bid/Ask quote ingestion and configurable MAX_SPREAD_POINTS hard gate.
- [ ] Add commission, slippage and session sensitivity to reports.
- [x] Add a research-only 1H Alpha flip replay with next-bar entry, cost assumptions, partial targets and conservative stop-first same-bar handling.
- [ ] Backtest the complete 4H/1H/15M/optional-5M strategy, then run walk-forward/out-of-sample and anti-repainting checks.
- [ ] Validate signal frequency and false-positive rate; never optimize only for win rate.

## Phase 5 — Web and Android delivery
- [x] Add MT5 EA-to-API candle bridge source and authenticated ingestion endpoint.
- [ ] Activate and verify the bridge with the user's MT5 terminal and server token; no live data is connected until this setup is completed.
- [x] Add POST /api/analysis/institutional-footprint and POST /api/analysis/gold-report endpoints (proxy/contract only; not live feed).
- [x] Add backend unit tests and GitHub Actions compile/test workflow; historical-data and frontend changes have green CI on their respective commits.
- [x] Connect dashboard to historical candle API, CSV import, 1H-primary report and initial 1H SMC overlays.
- [ ] Complete Bengali explanations, live data status and full interactive zone/risk panels.
- [x] Add PWA manifest, mobile metadata, icon, service-worker registration and offline app-shell cache (market data remains online; device install not yet manually verified).
- [ ] Android packaging only after web core, feed and validation are stable.
- [x] Add Docker API/web images, Compose deployment, environment template and deployment guide.
- [x] Add Docker image-build CI.
- [ ] Deploy to a real host with DNS/TLS, backups, monitoring and production secret management.

## Current verified state
- [x] React + Vite frontend foundation and build workflow.
- [x] FastAPI backend foundation.
- [x] Alpha Signal Engine initial port, endpoint and basic tests.
- [x] SMC, WSB and AI Channels first isolated OHLCV adapters with tests (not full Pine parity ports).
- [x] Gold Report AI orchestration combines all four indicator families and liquidity proxy.
- [x] Hierarchical 4H/1H/15M Decision Engine connected to calculated outputs; 1H is primary and 5M is optional.
- [x] Unified architecture and implementation status documented.
- [ ] Live feed has not yet been activated on the user's MT5 terminal; bridge code, quote/spread gate and setup guide are ready. Commission/slippage modelling, Android APK, live MBO/CVD/OI and validated backtesting remain pending. Certified Pine parity, calibrated/backtested trade planner, live MBO/CVD/OI feed, deployment and Android package remain pending. Historical CSV import, chart rendering and initial 1H candidate overlays are implemented.
- [ ] CI for the latest combined changes must be checked before claiming a green build.
