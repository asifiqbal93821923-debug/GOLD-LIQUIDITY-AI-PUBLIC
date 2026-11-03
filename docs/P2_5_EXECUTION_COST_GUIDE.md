# P2.5 — XM360 execution-cost evidence guide

P2.5 separates software correctness from broker-specific empirical validation. A passing unit test does not establish XM360 spreads, commission, slippage, or strategy profitability.

## Broker contract details to review

Capture the XM360 account type and exact XAUUSD contract symbol, contract size, point/tick size, minimum price increment, trading hours/server timezone, and commission schedule (per side or round turn, per lot). Do not assume the symbol is exactly XAUUSD or that a point is 0.01; use the actual account specification.

## Quote observation CSV

Place reviewed quote observations at data/phase2/xm360_quotes.csv with these exact columns:

    timestamp,bid,ask,point_size
    2026-01-05T06:00:00Z,4500.00,4500.10,0.01

The row above is only a format example, not a real quote or XM360 spread. Each timestamp must include Z or an explicit UTC offset. Do not interpolate missing observations or generate synthetic bid/ask values. Use a continuous capture spanning active sessions and rollover, and target at least 1,000 total quote samples; inspect per-session and rollover sample counts separately.

The workflow can run the audit when xm360_quotes.csv is present. Supply the rollover start/end in UTC only after confirming the broker's documented rollover schedule. The analyzer produces mean, median, P90/P95/P99 and maximum spread in points for fixed UTC diagnostic sessions and the configured rollover window. Fixed UTC buckets are not DST-adjusted market-session definitions.

## Costs required for scenario replay

- spread_points: reviewed broker spread assumption in the verified point size.
- max_spread_points: reviewed maximum acceptable spread. Keep it 0 until evidence is reviewed; P2.5 will then block entries with WAIT.
- slippage_points: conservative estimate supported by observed execution/fill differences, not quote spread.
- commission_points_per_side: broker commission converted to price points per side, using the correct contract size and account type.
- point_size: actual contract point size.

Base, conservative (+25% spread / +50% slippage) and adverse (+75% spread / +100% slippage / +25% commission) are controlled stress multipliers, not broker observations.

## Acceptance

Empirical P2.5 can be accepted only after:
1. Contract specification and the quote source are manually verified.
2. Session and rollover spread distributions have adequate samples.
3. Slippage and commission assumptions are supported by broker-specific evidence.
4. All three scenarios run on the same verified 4H/1H/15M history and reports are reviewed.
5. The maximum-spread cap is justified and configured.

OHLC backtests cannot reconstruct the true intrabar price path, queue position, or guaranteed fill. The replay therefore keeps conservative stop-first conflict handling and cannot be presented as live execution proof.
