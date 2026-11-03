# Engine 01 — Alpha Signal Engine Pro

Original author: MarkitTick. The supplied Pine source is licensed CC BY-NC-SA 4.0. This port and derivative modifications must retain attribution, remain non-commercial under that license, and be shared under the same license. Obtain separate permission before commercial use.

## Ported logic
1. Standard OHLCV candles only; Pine warns against Heikin-Ashi, Renko, Line Break, Kagi and Point & Figure.
2. Wilder ATR (Pine ta.atr) shifted one candle backward.
3. Volatility percentile buckets (Alpha/Beta/Gamma/Delta) and adaptive multipliers when enabled.
4. Price-move percentile cap, dynamic band width and EMA-smoothed band-half.
5. Recursive trend line and bullish/bearish direction.
6. Stall, regression slope, volume, candle-range percentile and BPS-delta filters.
7. Breakout override that bypasses a flat guard when its ATR threshold is exceeded.
8. Display direction holds its previous state during a flat guard; BUY/SELL are direction flips.
9. The API returns only the latest confirmed-candle state. It does not send orders.

## Pine parity notes
- Pine uses prior-bar ATR, close, high/low, volume and trend-line values in several places. Keep these offsets exactly when comparing.
- linreg offset-0 minus offset-1 is the regression slope.
- Nearest-rank percentile uses a ceiling rank.
- Warm-up / na behavior must be compared against TradingView with exported candles.
- Provider candle construction, timezone, volume meaning and missing-volume behavior can change outputs.
- The Python implementation is an initial port, not yet certified bit-for-bit identical. Do not rely on it for live trades until parity tests pass on the same OHLCV dataset.

## Not included in this source
No support/resistance, supply/demand, order-book footprint, institutional positions, entry zone, stop loss or TP1/TP2/TP3 are calculated by this indicator. These require separate engines and suitable data.

## Validation
Unit tests use deterministic synthetic candles only to validate the API contract and basic execution. They do not establish market accuracy or profitability. The next validation step is comparison against TradingView exports for multiple symbols/timeframes and settings.
