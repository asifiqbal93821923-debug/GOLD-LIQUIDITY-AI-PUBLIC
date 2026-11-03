# TradingView reference fixture procedure (Phase 2)

## Why this is required
The repository currently has synthetic OHLC unit-test fixtures, not a verified TradingView export. Therefore Python/Pine signal parity cannot honestly be marked complete yet.

## Export needed
From TradingView, export the same XAUUSD symbol/feed and chart settings used by the reference Pine strategy. Export separately for 4H, 1H, 15M and (if available) 5M. Include enough history for at least 100 closed candles per timeframe; more is preferred.

Required columns:
- timestamp (bar-open time; include timezone or Unix seconds)
- open
- high
- low
- close
- volume (only if the source provides it; do not treat it as real traded volume unless feed confirms that)

Also export the Pine strategy/indicator signal markers or a timestamp + BUY/SELL/WAIT reference table for 1H. Include exact script version and inputs.

## Comparison rules
- Compare only fully closed candles.
- Align each lower/higher timeframe bar by close time, not by row index.
- At each 1H decision close, 4H and 15M inputs must have close_time <= that 1H close.
- 5M is optional and may only refine/veto an immediate entry; it cannot create or reverse the 1H direction.
- Record timestamp, Pine direction, Python direction, mismatch reason, and whether the trade plan levels differ.

## Current status
- Automated synthetic unit tests verify time-boundary behavior and exclusion of forming candles.
- Real TradingView parity is pending an actual export from the user's selected chart/feed and exact Pine inputs.
- Synthetic test success is not evidence of trading edge or profitability.
