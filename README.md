# PROJECT INDICATOR APP

Independent XAUUSD (Gold) market-analysis application for **Web + Android**. TradingView is not required at runtime. The same responsive web client is intended to be installable as an Android PWA, with native packaging considered after the core app is stable.

## Product scope
- Independent candlestick chart with 1m, 5m, 15m, 30m, 1h, 4h and 1D views.
- Plain-language market state: bullish, bearish, range, momentum and breakout/breakdown.
- Support, resistance, supply and demand zones.
- Liquidity sweep and market-structure analysis, with clear distinction between measured facts and heuristics.
- BUY/SELL trade plans with entry zone, invalidation/stop loss, TP1/TP2/TP3 and confirmation/WAIT status.
- Pine Script source-code analysis and logic porting, validated against reference outputs and historical replay.

## Current status — Foundation 0.4.0 + 1H-primary analysis + historical import
- React + Vite responsive frontend and Lightweight Charts surface.
- FastAPI backend with health/configuration, SQLite historical-candle import/retrieval and analysis endpoints.
- Initial Alpha Signal Engine Pro Python port and API (parity pending).
- Source intake reviews for Alpha Signal, LuxAlgo SMC (partial source), WSB and AI Channels.
- Unified feature-selection architecture: [Unified Gold Engine Blueprint](docs/UNIFIED_GOLD_ENGINE_BLUEPRINT.md).
- 1H-primary Gold Report orchestrator: 4H macro context, 1H direction/trade-plan source, 15M setup confirmation and optional 5M refinement.\n- CSV historical-candle import, SQLite persistence, candlestick chart rendering and initial 1H SMC candidate-level overlays.\n- Authenticated MT5 Expert Advisor bridge for closed candles and Bid/Ask spread snapshots; actual live connection requires server token configuration and EA installation.\n- Installable PWA manifest, icon and offline app-shell cache; market/API data intentionally remains online-only.
- Explicit no-data state: the app does not invent candles or present demo values as live prices.

**Not yet complete:** actual MT5 bridge connection on the user's machine, live feed operational verification, full Pine parity, fully validated zones and trade planning, spread/cost model, backtesting, deployment and Android APK packaging. The current 1H ATR/structure plan is an uncalibrated proposal, not a validated trading system. This is an early engineering foundation, not a finished trading system.

## Market-data decision
Primary-source preference: use the user's own MT5 broker feed (through a secure server-side bridge) where practical, because it best matches the quote stream used for execution. A licensed external XAUUSD feed is the fallback. A provider will only be selected after checking symbol availability, WebSocket entitlement, historical depth, latency, terms and cost. Never expose provider API keys in the browser or commit secrets.

## Run locally

Backend:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r server/requirements.txt
uvicorn main:app --app-dir server --reload --host 127.0.0.1 --port 8765
```

Frontend:
```bash
cd web
npm install
npm run dev
```

The Vite development server proxies `/api` to the local FastAPI server.\n\n### Import historical candles\nUse the dashboard CSV importer for the selected timeframe. Required headers: `time,open,high,low,close`; optional `volume`. `time` accepts Unix seconds/milliseconds or ISO timestamps. Imported candles are stored locally in SQLite and are explicitly historical, not live. For MT5 desktop streaming, see [MT5 Bridge Setup](docs/MT5_BRIDGE_SETUP.md) and compile [GoldLiquidityBridge.mq5](mt5/GoldLiquidityBridge.mq5). Set `MARKET_INGEST_TOKEN` on the server and the same token in EA inputs; do not commit the token. Supported endpoint: `POST /api/market/candles/import`; retrieve with `GET /api/market/candles?timeframe=1h&limit=3000`.

## Security and trading safeguards
- Store secrets in server environment variables only.
- No broker order execution in the initial release.
- No signal is a guarantee of profit or personalized investment advice.
- Prefer closed-candle confirmation and test for repainting/look-ahead bias.
- Historical tests must account for spread, commission, slippage and session differences.
- Candle-based liquidity heuristics do not reveal all OTC pending orders, bank order books or actual institutional positions.
- True footprint/volume-at-price requires suitable trade-level or volume-at-price data.

See [Architecture](docs/ARCHITECTURE.md) and [Roadmap](docs/ROADMAP.md).
