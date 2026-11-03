# Timestamped SMC shaded zones

## What is implemented

The SMC adapter emits candle-derived zone records with:
- `zone_type`: `fvg` or `order_block`
- `direction`: `bullish` (demand) or `bearish` (supply)
- `low` / `high`: the price bounds
- `start_time`: epoch seconds for the candle that formed the zone, when source time is valid
- `status`: `active`, `mitigated`, or `invalidated`

FVG zones come from the three-candle gap rule. An OB candidate is the last opposite-colour candle found before the adapter's current confirmed structure break. This is a deliberately limited OHLCV adapter, not a complete LuxAlgo port.

## Lifecycle rules

- FVG: any later candle overlapping the zone marks it mitigated; a later close through the far boundary marks it invalidated (invalidation takes precedence).
- OB candidate: any later overlap marks it mitigated; a later close beyond the distal boundary marks it invalidated (invalidation takes precedence).
- The API retains recent zones and their lifecycle state for inspection.
- Only `active` zones are drawn as shaded rectangles. Mitigated and invalidated zones remain visible in Zone Radar with their status.
- The chart anchors each rectangle to the actual source candle time and price bounds; it does not fabricate an x-coordinate when the timestamp is missing.

## Multi-timeframe display

The main chart overlays recent zones from 4H (macro), 1H (primary), and 15M (setup). Zone labels identify timeframe, zone type and supply/demand direction. This is a visual context layer; it does not change the decision engine's 1H direction hierarchy.

## Important limits

These are candle-derived candidates only. They do not reveal bank identity, actual pending orders, exchange order-book depth, MBO, iceberg orders, true aggressor-side delta, or true CVD. Spot/CFD XAUUSD volume may be broker tick volume. The adapter is not Pine-parity certified; compare it with TradingView-exported fixtures and test on real broker candles before relying on it.

## Tests

`server/tests/test_smc_zone_lifecycle.py` checks epoch timestamp anchoring, ISO-8601 timestamp conversion, and invalidation by a close through the zone boundary.
