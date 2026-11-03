# Project Indicator App — Architecture

## Product
A standalone XAUUSD analysis application for Web and Android (PWA first, native packaging later). TradingView is not a runtime dependency.

## Implemented foundation
- React + Vite responsive client and Lightweight Charts surface.
- FastAPI health, configuration-status and candle-contract endpoints.
- Initial Alpha Signal Engine Pro calculation port, API and unit tests (TradingView parity pending).
- Initial WAIT-first unified decision gate and API endpoint. It validates already-computed evidence; it does not yet calculate the upstream indicators.

## Planned modules
1. Market data adapters: provider-neutral interface; evaluate broker MT5 bridge and licensed market-data WebSocket providers before choosing production feed.
2. Candle normalizer and timeframe aggregator: symbol, timeframe, timezone, OHLCV, source metadata, completed-bar boundaries and gap checks.
3. Isolated feature engines: Alpha trend/volatility; SMC structure/liquidity; WSB wick/absorption/breakout; AI Channels price-distribution context.
4. Context layer: sweep/reclaim, displacement, FVG and supply/demand freshness/mitigation/invalidation.
5. Confluence decision: 4H macro bias + 1H main bias + 15M setup + 5M trigger, with WAIT-first gates and correlated-feature controls.
6. Trade planner: entry range, invalidation/SL, TP1-TP3, risk/reward and WAIT state.
7. Replay/backtest: historical candles, no-lookahead checks, fees/spread assumptions, walk-forward and out-of-sample reports.
8. Bengali-first dashboard overlays and explanations.
9. PWA installability and Android package after data and analysis core are stable.

## Important constraints
- OTC spot Gold is fragmented; a provider quote may differ from the user's MT5 broker.
- Candles alone cannot reveal every pending order, bank order book or institutional position.
- WSB volume split is a close-location estimate, not bid/ask delta.
- AI Channels is a context filter, not an entry signal.
- No broker order execution in the initial product.
- Signals must be timestamped and non-repainting where possible; closed-candle confirmation is preferred.
- Preserve each source's attribution and license; the supplied LuxAlgo SMC source is incomplete and blocks a full port.
