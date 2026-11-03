# Project Indicator App — Architecture

## Product
A standalone XAUUSD analysis application for Web and Android (PWA first, native packaging later). TradingView is not a runtime dependency.

## Implemented foundation
- React + Vite responsive client and Lightweight Charts surface.
- FastAPI health/configuration plus persistent SQLite historical-candle import/retrieval endpoints with OHLC validation.
- Initial Alpha Signal Engine Pro calculation port, API and unit tests (TradingView parity pending).
- 1H-primary Gold Report pipeline: 4H macro veto/context, 1H primary direction and initial risk-plan source, 15M setup confirmation, optional 5M entry refinement.
- Web dashboard consumes imported historical or recently bridged MT5 candles, plots OHLC candles, and overlays initial 1H SMC candidate levels on the main chart.
- Authenticated MT5 Expert Advisor bridge for closed candles and Bid/Ask quotes, with configurable spread hard gate; user-side MT5/server configuration is still required.
- PWA manifest, service worker and offline app-shell cache are implemented; market/API data intentionally remains online-only.
- Research-only 1H Alpha replay supports next-bar entries, partial target exits, stop-first same-bar handling and configurable execution costs.

## Planned modules
1. Market data adapters: historical CSV/JSON ingestion is implemented; provider-neutral live adapter and broker MT5 bridge/licensed WebSocket remain pending.
2. Candle normalizer and timeframe aggregator: symbol, timeframe, timezone, OHLCV, source metadata, completed-bar boundaries and gap checks.
3. Isolated feature engines: Alpha trend/volatility; SMC structure/liquidity; WSB wick/absorption/breakout; AI Channels price-distribution context.
4. Context layer: sweep/reclaim, displacement, FVG and supply/demand freshness/mitigation/invalidation.
5. Confluence decision: 4H macro context/veto + 1H primary bias and trade plan + 15M setup + optional 5M entry refinement, with WAIT-first gates and correlated-feature controls.
6. Trade planner: entry range, invalidation/SL, TP1-TP3, risk/reward and WAIT state.
7. Replay/backtest: an initial single-engine 1H Alpha replay is implemented; full multi-timeframe replay, no-lookahead certification, calibrated broker costs, walk-forward and out-of-sample reports remain pending.
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
