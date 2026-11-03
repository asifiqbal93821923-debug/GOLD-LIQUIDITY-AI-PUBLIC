# PROJECT INDICATOR APP

Independent XAUUSD (Gold) market-analysis application for **Web + Android**. TradingView is not required at runtime. The same responsive web client is intended to be installable as an Android PWA, with native packaging considered after the core app is stable.

## Product scope
- Independent candlestick chart with 1m, 5m, 15m, 30m, 1h, 4h and 1D views.
- Plain-language market state: bullish, bearish, range, momentum and breakout/breakdown.
- Support, resistance, supply and demand zones.
- Liquidity sweep and market-structure analysis, with clear distinction between measured facts and heuristics.
- BUY/SELL trade plans with entry zone, invalidation/stop loss, TP1/TP2/TP3 and confirmation/WAIT status.
- Pine Script source-code analysis and logic porting, validated against reference outputs and historical replay.

## Current status — Foundation 0.3.0 + initial decision gate
- React + Vite responsive frontend and Lightweight Charts surface.
- FastAPI backend with health/configuration/candle endpoints.
- Initial Alpha Signal Engine Pro Python port and API (parity pending).
- Source intake reviews for Alpha Signal, LuxAlgo SMC (partial source), WSB and AI Channels.
- Unified feature-selection architecture: [Unified Gold Engine Blueprint](docs/UNIFIED_GOLD_ENGINE_BLUEPRINT.md).
- Initial WAIT-first confluence module and POST /api/analysis/unified-decision endpoint. It accepts precomputed, confirmed timeframe/structure/trigger evidence and a valid risk plan; it does not yet calculate those inputs itself.
- Explicit no-data state: the app does not invent candles or present demo values as live prices.

**Not yet complete:** production market feed, complete indicator ports, TradingView parity, automatic structure/zones, calculated entry/SL/TP, backtesting, deployment and Android packaging. This is an early engineering foundation, not a finished trading system.

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

The Vite development server proxies `/api` to the local FastAPI server.

## Security and trading safeguards
- Store secrets in server environment variables only.
- No broker order execution in the initial release.
- No signal is a guarantee of profit or personalized investment advice.
- Prefer closed-candle confirmation and test for repainting/look-ahead bias.
- Historical tests must account for spread, commission, slippage and session differences.
- Candle-based liquidity heuristics do not reveal all OTC pending orders, bank order books or actual institutional positions.
- True footprint/volume-at-price requires suitable trade-level or volume-at-price data.

See [Architecture](docs/ARCHITECTURE.md) and [Roadmap](docs/ROADMAP.md).
