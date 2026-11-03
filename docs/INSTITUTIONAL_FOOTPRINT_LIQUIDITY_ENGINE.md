# Institutional Footprint & Liquidity Intelligence

## Purpose
This module adds the seven requested institutional-liquidity views to GOLD REPORT AI. It deliberately separates verified exchange data from OHLCV-derived estimates.

## Seven feature groups and current implementation

| Feature | Current state | Evidence / limitation |
|---|---|---|
| 1. Live order book / MBO | Not connected | No resting order sizes or queue positions are reported. Requires licensed venue-specific market-by-order data and entitlements. |
| 2. Liquidity heatmap | Initial OHLCV proxy implemented | Confirmed swing-high/swing-low clusters are displayed as estimated liquidity pools, not resting limit orders. |
| 3. Buyer/seller footprint | Partial proxy implemented | Candle range, wick, relative volume and close-location estimated buy/sell activity. No true bid/ask footprint. |
| 4. Iceberg / hidden liquidity | Not implemented | Requires order-level replenishment or suitable trade/order feed; wick patterns alone cannot prove iceberg orders. |
| 5. Stop-loss/liquidity pools | Initial proxy implemented | Confirmed pivots, repeated highs/lows and sweep/reclaim patterns. Actual stop orders are not visible. |
| 6. CVD / OI / large prints | Partial proxy implemented | Estimated candle-location delta and rolling 20-bar estimate only. Open interest and large trade tape remain unavailable. |
| 7. Institutional activity score | Initial proxy implemented | Rule-based OHLCV score with low confidence. It is not a probability and never triggers a trade by itself. |

## API
- POST /api/analysis/institutional-footprint
  - Input: chronological OHLCV candles (minimum 30) and optional settings.
  - Output: estimated liquidity pools, heatmap levels, sweep/reclaim, volume anomaly, candle-location delta, absorption proxy, activity score and data-quality caveats.
- POST /api/analysis/gold-report
  - Input: timeframes object with any available 4h, 1h, 15m, 5m candle arrays.
  - Output: four-timeframe footprint report. Missing timeframe data stays unavailable; decision remains WAIT.

## Critical semantics
- estimated_buy_volume, estimated_sell_volume, estimated_delta and estimated_cvd_20_bars are heuristics based on candle close location. They are not exchange aggressor-side volume or true CVD.
- Spot/CFD XAUUSD broker volume is often tick/activity volume, not centralized traded quantity.
- CME Gold Futures order book data is a separate market from a broker's OTC XAUUSD CFD quote. It can be used as a reference only after symbol, contract, session and timestamp alignment.
- CME MBO can expose anonymous order-level detail, not the named company behind an order.
- A visible order can be cancelled; displayed depth is not guaranteed execution.
- Never convert these proxy outputs into a BUY/SELL without the separate 4H/1H/15M/5M trend, structure, trigger and risk gates.

## Required next steps
1. Select and license a specific market data vendor and exact product (CME MDP/MBO or equivalent); verify redistribution and display rights.
2. Implement a server-side provider adapter, reconnect/heartbeat, sequence-gap recovery, exchange timestamps and symbol/contract mapping.
3. Add order-book snapshots/deltas, depth heatmap, order add/cancel/execute tracking and queue-aware replay.
4. Add trade prints to compute true aggressor-side delta/CVD where the feed supports it; keep OI as a separate periodic dataset.
5. Add iceberg/replenishment heuristics only where the feed provides enough order identity/sequence detail.
6. Add historical event replay, golden fixtures, unit tests and feed-gap/reconnect tests.
7. Validate CME futures reference vs XAUUSD broker feed; do not imply the two books are identical.
8. Keep the order-flow score informational until walk-forward and out-of-sample calibration is complete.

## Status
The first backend proxy engine and API contracts are committed. It is not a live order-book connection, not a complete seven-feature production system, and not parity/backtest certified. No live provider credentials have been configured.
