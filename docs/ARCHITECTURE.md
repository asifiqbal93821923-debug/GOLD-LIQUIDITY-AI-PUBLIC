# Project Indicator App — Architecture (Foundation)

## Product
A standalone XAUUSD analysis application for Web and Android (PWA first, native packaging later). TradingView is not a runtime dependency.

## Current foundation
- React + Vite responsive client.
- TradingView Lightweight Charts library for the independent chart surface.
- FastAPI backend with health, configuration-status and candle-contract endpoints.
- Provider credentials stay on the server and are never sent to the browser.
- Empty data is explicit: the app must not label generated/demo prices as live.

## Planned modules
1. Market data adapters: provider-neutral interface; evaluate broker MT5 bridge and licensed market-data WebSocket providers before choosing production feed.
2. Candle normalizer: symbol, timeframe, timezone, OHLCV and source metadata.
3. Pine logic adapter: translate the supplied Pine Script feature-by-feature and compare outputs against TradingView exports.
4. Analysis engine: trend, momentum, market structure, supply/demand, liquidity heuristics and confidence/confirmation states.
5. Trade planner: entry range, invalidation/SL, TP1-TP3, risk/reward and WAIT state.
6. Replay/backtest: historical candles, no-lookahead checks, fees/spread assumptions and performance report.
7. PWA installability and Android package.

## Important constraints
- OTC spot Gold is fragmented; a provider quote may differ from the user's MT5 broker.
- Candles alone cannot reveal every pending order, bank order book or institutional position.
- Footprint/volume-at-price requires suitable trade-level or volume-at-price data.
- No order execution in the initial product.
- Signals must be timestamped and non-repainting where possible; closed-candle confirmation is preferred.
