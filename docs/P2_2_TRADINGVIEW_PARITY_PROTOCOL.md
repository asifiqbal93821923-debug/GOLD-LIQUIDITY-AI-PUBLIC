# P2.2 — TradingView/Python Pine parity protocol

## Scope
Run parity separately for each Pine script/version and timeframe. Do not mix:
- PRO XAU V2.0 (strategy; 15M entries with 1H confirmation)
- Advanced SMC MTF Pro (indicator; 1H primary zones with 4H context)
- Alpha Signal / any other indicator

A Python port is not considered matched merely because it produces similar-looking chart marks.

## Required TradingView exports
For every script + timeframe combination, export one CSV row for every chart bar, not only alert events:
- `time`: bar OPEN timestamp, UTC Unix seconds (or ISO-8601 with timezone)
- `signal`: BUY / SELL / WAIT
- optional numeric output columns (e.g. trend_line, atr, upper_band, lower_band, demand_top, demand_bottom, supply_top, supply_bottom)

Export only confirmed/closed bars. Include WAIT rows so missed signals can be detected.

## Exact metadata (one JSON per fixture)
Copy actual values from the TradingView chart and Pine settings panel:
```json
{
  "script_title": "EXACT title shown by TradingView",
  "pine_version": "6",
  "symbol": "EXACT ticker, e.g. OANDA:XAUUSD",
  "provider": "EXACT provider shown by chart",
  "timezone": "Etc/UTC",
  "timeframe": "1h",
  "bar_timestamp": "bar_open",
  "bar_confirmation": "barstate.isconfirmed",
  "settings": {
    "input_name_as_shown_in_pine": "exact selected value"
  }
}
```
Do not fill example values unless they are actually the chart's values. For a strategy, also record strategy properties (initial capital, order size, commission, slippage, pyramiding, process_orders_on_close, calc_on_order_fills).

## Python side
Export the matching engine's per-bar signal series using the exact same OHLCV file, timestamps and settings. Store a candidate metadata JSON using the same schema.

## Run
```bash
python scripts/compare_tradingview_signals.py \
  --reference data/phase2/pine_reference_1h.csv \
  --candidate reports/phase2/python-signals-1h.csv \
  --reference-meta data/phase2/pine_reference_1h.meta.json \
  --candidate-meta reports/phase2/python-signals-1h.meta.json \
  --output reports/phase2/tradingview-parity-1h.json
```

Optional numeric-series check:
```bash
--numeric-columns trend_line,atr,upper_band,lower_band --numeric-tolerance 0.000001
```

## PASS gate
- metadata matches exactly;
- no missing/extra timestamps;
- every bar signal matches (BUY/SELL/WAIT);
- every selected numeric output is within declared tolerance;
- fixtures identify exact Pine source version and settings.
A high direction-accuracy percentage is diagnostic only; it is not a PASS.

## Current limitation
The repository's existing Python Alpha adapter documents its upstream Alpha Signal Pine lineage. That does not establish parity for PRO XAU V2.0 or Advanced SMC MTF Pro. Those scripts' exact source, TradingView settings and per-bar exports must be supplied/exported before those engines can be matched honestly.
