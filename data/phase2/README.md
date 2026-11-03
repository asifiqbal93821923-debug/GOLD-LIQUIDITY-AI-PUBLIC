# Phase 2 historical data input

Place these TradingView Export chart data CSV files in this folder, all from the exact same provider/feed and XAUUSD ticker:

- xauusd_4h.csv
- xauusd_1h.csv
- xauusd_15m.csv
- Optional: xauusd_5m.csv
- Optional Pine reference signal export: pine_reference_1h.csv

The three required timeframe exports must include time,open,high,low,close columns. volume is optional and is never presumed to be true traded volume. Timestamps must be Unix seconds/milliseconds or timezone-aware ISO timestamps. Export closed candles only.

The operator must verify that the chart header, ticker and provider are identical across the exports, and pass those exact labels to the GitHub Actions workflow. The labels do not independently prove the source. Do not combine OANDA, TVC, broker MT5, Dukascopy or other feeds in one dataset.
