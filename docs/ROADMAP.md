# Development Roadmap — XAUUSD Gold Report AI

Last reconciled: 2026-11-03

## A. Market data and MT5 connectivity

- [x] SQLite candle database with validated historical OHLCV import/retrieval.
- [x] CSV import from the dashboard; no synthetic/demo prices are fabricated.
- [x] Authenticated MT5 EA candle bridge for closed 4H, 1H, 15M and 5M candles.
- [x] MT5 Bid/Ask quote bridge with actual last-tick timestamp.
- [x] Server freshness checks: each required candle timeframe must be recently ingested and the actual broker tick timestamp must be recent and non-future; configurable `MAX_SPREAD_POINTS` hard gate.\n- [x] Dashboard live badge and quote API now use the same server-side candle/tick freshness rules; client-supplied freshness flags cannot open the trade gate.
- [x] MT5 setup instructions and Docker environment template.
- [ ] User must configure a private server token and install/compile the EA in MT5 desktop or VPS.
- [ ] Verify broker symbol suffix, server timezone, candle boundaries, session gaps and volume semantics with the user's real feed.
- [ ] Activate a licensed external feed only if MT5 bridge is unsuitable; no external provider credentials are configured.

## B. Indicator engines and Decision Engine

- [x] Alpha Signal Engine Pro initial Python adapter, endpoint and tests.
- [x] SMC structure adapter: confirmed pivots, BOS/CHoCH, EQH/EQL, FVG/OB candidates and premium/discount context.
- [x] WSB wick/absorption/breakout adapter.
- [x] AI Channels K-means context adapter.
- [x] Institutional Footprint OHLCV proxy: liquidity clusters, sweep/reclaim and activity estimates.
- [x] Unified Decision Engine: 4H macro veto, 1H primary direction/risk plan, 15M setup, optional 5M refinement.
- [x] Gold Report AI orchestration combines all adapters.
- [x] Ambiguous 1H structure and opposing confirmed 5M trigger hard-vetoes.
- [ ] Full source-code parity with all supplied Pine scripts; current adapters are not parity-certified.
- [ ] TradingView-exported golden fixtures for every engine and edge-case comparison.
- [ ] Corrected SMC MTF no-lookahead/repainting, array-removal and bounded-history behavior.
- [ ] Licensed exchange order-book/MBO, true aggressor-side CVD, open interest and trade-print feeds. Current OHLCV proxies are not real institutional orders or true CVD.
- [ ] Calibrate evidence weights only after out-of-sample testing.

## C. Chart and dashboard

- [x] Responsive React/Vite dashboard and Lightweight Charts candlestick chart.
- [x] Timeframe selection for 3M, 5M, 15M, 30M, 1H, 4H and 1D.
- [x] 1H is the default and primary trading timeframe.
- [x] 4H macro swing levels and 1H swing/FVG/OB-candidate/EQH/EQL price levels are drawn on the main chart across chart views.
- [x] Bengali-first Gold Report panel with BUY/SELL/WAIT, reason codes and 1H entry/SL/TP proposal.
- [x] Historical CSV import, data status, quote/spread status and backtest result panels.
- [x] Timestamped OHLCV-derived FVG/OB zone lifecycle (active/mitigated/invalidated) and shaded 4H/1H/15M overlays on the main chart; not verified institutional resting orders.
- [ ] Prior day/week/month levels, richer liquidity sweep annotations and multi-timeframe zone labels.
- [ ] Full per-engine Bengali evidence explanations and accessible mobile refinements.
- [ ] Visual validation on actual Android device sizes and slow network.

## D. Trade planning and historical validation

- [x] Initial 1H structural/ATR entry zone, stop and TP1/TP2/TP3 proposal.
- [x] Research-only 1H Alpha flip replay with next-bar entry, partial targets and conservative stop-first same-bar handling.
- [x] Editable spread, slippage and commission assumptions in the research replay.
- [x] First causal 4H/1H/15M/optional-5M Gold Report replay endpoint and dashboard UI.
- [x] MTF replay aligns only fully closed bars available at each 1H decision close to reduce future leakage.\n- [x] MTF replay excludes currently forming/future candles before simulation and reports exclusion counts.
- [ ] Validate MTF replay against TradingView golden fixtures and independently inspect every time-alignment edge case.
- [ ] Calibrate entry zone/ATR/stop/targets; current plan is an uncalibrated research proposal.
- [ ] Walk-forward, out-of-sample and anti-repainting validation.
- [ ] Spread/commission/slippage scenario sweeps, session sensitivity and realistic broker execution assumptions.
- [ ] Evaluate trade frequency, false positives, expectancy, drawdown and robustness; do not optimize only win rate.
- [ ] Paper-trading forward test before any real-money use.

## E. Packaging and operations

- [x] PWA manifest, mobile metadata, app icon, service-worker registration and offline app-shell cache.
- [x] Docker API/web images, Docker Compose, environment template and deployment guide.\n- [x] Compose waits for the API health check before starting the web service; CI validates Compose configuration and builds both images.
- [x] GitHub Actions backend tests, frontend build and Docker image-build workflows.
- [ ] Verify the PWA install manually on the user's Android device over HTTPS.
- [ ] Deploy to a real VPS/host with DNS, TLS, secret management, monitoring, backups and log retention.
- [ ] Build and sign a native Android APK after feed, strategy validation and web core are stable.
- [ ] Install/test native package on a real Android device.

- Shaded zone overlay now uses each zone's source-candle epoch timestamp and price bounds; only active zones are painted, while the Zone Radar lists lifecycle state. Missing/invalid timestamps prevent drawing rather than fabricating placement.\n\n## Current verification boundary

- Backend syntax and unit tests have passed on the latest backend feature commits, including the causal MTF replay and stale-tick spread gate.
- Frontend production build has passed after the MTF replay panel and 4H/1H price overlays.
- Docker build workflow is part of CI; verify the newest run before declaring the latest docs-only commit fully green.
- MT5 EA source is committed but has not been compiled in MetaEditor or connected to the user's broker terminal.
- No real broker feed is currently confirmed. No live institutional order book, MBO, true CVD or OI feed is connected.
- The app does not place broker orders. No BUY/SELL output should be treated as a profit guarantee.


## F. Phase 3 — Risk controls, alerts and trade records

- [x] Remove the Phase 2 research acceptance tracker from the main dashboard; Phase 2 research files and workflows remain available as engineering reference.
- [x] Add a persistent risk profile using the same configured SQLite/PostgreSQL database as historical candles.
- [x] Enforce TP1 minimum reward/risk, maximum trades/day, maximum open trades, cooldown, optional stricter user spread ceiling and daily-loss limit when balance is configured.
- [x] Calculate a position-size estimate only when account balance and exact broker contract size are explicitly configured.
- [x] Add confirmed 1H signal events with direction-transition deduplication and durable alert history.
- [x] Add optional browser notifications with explicit user permission.
- [x] Add a persistent manual trade journal with open/close status, exit price and user-entered realized PnL.
- [ ] Validate persistence on the deployed database by writing settings and a test journal record, then reading after restart.
- [ ] Verify Phase 3 UI on the real Android browser and notification permission behavior.
- [ ] Verify the user's authenticated MT5 feed and broker-calibrated server spread cap before claiming live alerts are operational.

Phase 3 is an analysis, risk-control and recordkeeping layer. It does not place, modify or close broker orders. Institutional MBO/order-book, true CVD, OI and iceberg detection still require licensed feeds.


## G. Phase 4 — one-call validation and dashboard cleanup (2026-11-04)

- [x] Remove the visible Alpha Signal Research Backtest card and its fields/actions from the dashboard.
- [x] Remove the visible manual Trade Journal card, create/close fields and journal-linked dashboard counters. Existing storage/API records are preserved for compatibility and are not deleted.
- [x] Add a server-side Phase 4 API and one dashboard action for data preflight, historical data audit, causal MTF replay, three execution-cost scenarios, walk-forward folds and a sealed holdout.
- [x] Repair walk-forward OOS warm-up: each test/holdout window receives up to 50 prior candles per timeframe, while an OOS start gate prevents context-only signals from being counted.
- [x] Add Phase 4 preflight and warm-up separation tests.
- [ ] Run the full validation on same-provider XAUUSD 4H/1H/15M/optional-5M source exports. No such user data bundle was supplied to this run.
- [ ] Compare all relevant outputs with confirmed-bar TradingView exports and exact Pine version/settings; parity remains uncertified.
- [ ] Replace assumed costs with timestamped broker-observed spread, slippage, commission and point-size evidence.
- [ ] Verify authenticated MT5 feed and perform a persistent forward paper test.
- [ ] Verify GitHub Pages and Render deployment after CI/deploy workflows complete.

Phase 4 code completion is not strategy certification. The report remains NOT_CERTIFIED until data provenance, TradingView parity, broker costs, live MT5 and forward paper evidence are independently verified.
