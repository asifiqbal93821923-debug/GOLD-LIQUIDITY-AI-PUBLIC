# Trading validation tools — operator guide

These tools are committed as validation infrastructure. They do not make a strategy profitable or establish TradingView parity without matching reference data.

## 1. TradingView signal parity

Export a TradingView CSV with `time,signal` columns. Use UTC Unix seconds or ISO-8601 timestamps. Signal values: BUY/SELL/WAIT. Generate a second CSV from the Python engine with the same symbol, feed, closed-bar convention and period.

```bash
python scripts/compare_tradingview_signals.py --reference tv_signals.csv --candidate engine_signals.csv --tolerance-seconds 0 --output parity.json
```

Compare missed/extra events and direction mismatches. Do not compare signals from different brokers/feed or differing Pine inputs. OHLC export alone cannot establish indicator parity; export the actual Pine signal events and provide the exact Pine version/inputs.

## 2. Historical calibration and costs

Supply genuine broker/TradingView OHLC candle JSON with arrays `4h`, `1h`, `15m` and optional `5m`. Every row has `time,open,high,low,close,volume`; timestamps are UTC bar-open times. Use the same source/feed for every timeframe. Do not label sampled XAUS spot as broker OHLCV.

The existing replay accepts explicit `point_size`, `spread_points`, `slippage_points`, `commission_points_per_side` and `max_spread_points`. These are user-supplied broker assumptions. Calibrate only on the training window; never tune using the holdout.

## 3. Walk-forward

```bash
python scripts/walk_forward_validation.py --input xau_ohlc.json --train-fraction 0.70 --spread-points 25 --slippage-points 3 --commission-points-per-side 0 --point-size 0.01 --output walk-forward.json
```

The harness performs a chronological fixed-parameter train/holdout replay. It is not an optimizer and does not yet implement rolling parameter re-optimization. Both partitions must independently contain at least 50 fully closed candles per required timeframe; for 70/30 split, at least 167 bars per timeframe are needed. A much larger sample is recommended.

## 4. Paper-trading ledger

For each new closed 1H candle, supply the latest unified decision JSON and the next closed candle OHLC JSON:

```bash
python scripts/paper_trade_ledger.py --ledger data/paper-trades.json --decision decision.json --candle next_1h_candle.json --spread-price 0.20 --slippage-price 0.05
```

It records hypothetical entries only when the next candle open is inside the 1H entry zone, applies spread/slippage assumptions, and resolves stop/target on supplied OHLC. It never sends broker orders. Run it continuously from a trusted scheduler or backend; a repository commit alone does not make a live paper trader. Use broker-matched Bid/Ask OHLC if available. Sampled indicative spot prices are not suitable for reliable fill simulation.

## Current validation state

- Framework and unit tests: implemented.
- Actual TradingView parity result: blocked until the user's same-feed Pine signal export and settings are supplied.
- Historical calibration / walk-forward metrics: blocked until sufficient genuine 4H/1H/15M OHLC history and realistic cost assumptions are supplied.
- Paper trading: ledger implemented; forward observation period has not yet elapsed and must be run with a continuous data feed.
