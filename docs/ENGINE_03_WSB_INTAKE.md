# Engine 03 — Wick Sequence Breakout (WSB) Intake

## Source identity and license
- Indicator: Wick Sequence Breakout (WSB)
- Author: Uncle_the_shooter
- Pine Script: v6
- License header: Mozilla Public License 2.0 (MPL-2.0), https://mozilla.org/MPL/2.0/
- Keep author attribution and the MPL-2.0 notice with any covered source file or derivative implementation. Review MPL file-level source-disclosure obligations before distribution. Do not relicense this engine as proprietary.

## Intake status
- Full source received in the conversation, including formation tracking, breakout logic, volume allocation, TP/SL drawings, plots and alerts.
- Status: logic reviewed; not yet ported or parity-certified. No claim of Pine-equivalent output until exported OHLCV fixtures and settings are compared.

## Core calculations
1. Candle geometry: range = high - low; upper/lower wick percentages are measured against full range. Zero-range candles receive zero wick percentages.
2. Wick candidates:
   - Bearish: upper wick share >= configured minimum and lower wick share <= configured maximum.
   - Bullish: lower wick share >= configured minimum and upper wick share <= configured maximum.
   - Candle body direction is deliberately ignored for wick candidates.
3. Optional ATR size gate: wick candles count only when range >= ATR × minimum multiplier.
4. Absorption candidates: enabled only with usable volume; volume >= SMA(volume) × multiplier and range <= ATR × max-small-range. Direction uses qualifying wick shape first; otherwise close location within candle range. Indecisive closes are ignored.
5. Formation window: count bearish, bullish and any qualifying candles over the latest N bars. Bearish/bullish patterns require one side to qualify without the other; optional mixed formation requires total count but neither side alone qualifies. Creation occurs on the raw pattern's rising edge.
6. Formation bounds: highest high and lowest low across the configured window. Concurrent formations are stored independently, subject to a maximum count. Mixed formations are suppressed when a recent active formation overlaps the same window.
7. Approximate volume split: for each candle overlapping the formation range, allocate volume proportionally by close location: bull += volume × (close-low)/range; bear += volume × (high-close)/range. Breakout candle is excluded from accumulated formation volume.
8. Breakout: compare close or wick to formation top/bottom. A valid signal requires breakout direction to agree with dominant accumulated estimated volume. Optional breakout-size filter gates signal generation, not formation resolution.
9. Lifecycle: valid formations finalize, mismatched-direction formations are deleted or neutralized, and timed-out formations are deleted or retained as expired.

## Candidate app features (recommended)
- Wick rejection sequence score (bullish/bearish) over a configurable rolling window.
- High-volume, low-range absorption candidate with close-location direction.
- Formation high/low range and breakout/retest context.
- Estimated buy/sell volume split as a clearly labelled candle-derived heuristic only.
- Breakout confirmation mode: close-based default; wick-based optional.
- Breakout candle expansion filter versus prior average range.
- Formation expiry and concurrent-setup controls.
- Optional risk-distance calculator based on ATR or percentage, with configurable RR targets.

## Important implementation and validation caveats
- This is a candle/volume heuristic, not exchange bid/ask delta, footprint, resting liquidity, or verified institutional order flow. On spot/CFD XAUUSD, volume may be broker tick volume; expose volume provenance and disable absorption when volume is missing/unreliable.
- Pine's series indexing, SMA/ATR warm-up, rising-edge behavior, array iteration order, and bar-index timing must be replicated explicitly.
- The source's volume split is a close-location allocation, not true buyer/seller volume. Label it "estimated pressure" or "candle-derived volume split", never "real buy/sell volume".
- When one candle crosses both formation boundaries, both breakout directions may be true. The original script can produce opposite signals from different concurrent formations on one bar; its TP/SL block intentionally draws no levels when both directions fire. App logic should flag this as ambiguous and return WAIT rather than choose arbitrarily.
- Breakout-size filter is evaluated on the current bar for all active formations.
- maxWaitBars expires only when elapsed bars are strictly greater than the setting; preserve or intentionally document any change.
- Original TP/SL uses signal close as entry and ATR/percent distance for SL and RR targets. Its active trade termination checks the furthest enabled TP target (TP3, else TP2, else TP1) plus SL. If SL and target are both touched in one OHLC candle, intrabar ordering is unknowable; backtests must use conservative stop-first handling or lower-timeframe data.
- The original drawings are not needed in the backend engine. Return structured zones/events and render them in the app chart.
- Avoid counting wick sequence, absorption, breakout expansion and volume split as four independent confirmations without correlation controls; they are related observations from the same candles.

## Proposed normalized output
- engine_id: wsb
- formation_type: bullish | bearish | mixed
- formation_start_time / formation_confirmed_time
- formation_high / formation_low
- qualifying_wick_count_bull / qualifying_wick_count_bear
- absorption_count_bull / absorption_count_bear
- estimated_bull_pressure / estimated_bear_pressure
- breakout_direction: bullish | bearish | none | ambiguous
- breakout_basis: close | wick
- breakout_size_pass
- expiry_state
- optional entry_reference, stop_loss, take_profit_1/2/3, risk_reward
- explanation and data_quality flags

## Required tests before enabling in confluence
- Wick percentages at boundaries, zero-range bars and doji bodies.
- ATR filter on/off and ATR warm-up.
- Absorption with/without volume, missing volume, threshold equality and indecisive close.
- Window counts, overlapping bullish/bearish candidates, mixed patterns and rising-edge creation.
- Concurrent formation cap and recent-active mixed suppression.
- Volume allocation for overlapping/non-overlapping candles and zero-volume data.
- Close versus wick breakout; dominant-volume agreement; equal-volume tie behavior.
- Both-side breakout ambiguity; breakout-size filter; expiry boundary.
- TP/SL distances for long/short, ATR warm-up, and same-bar SL/TP collision.
- Compare against TradingView exports on identical symbol, timeframe, session, OHLCV and input settings.

## Integration decision
Accept as a separate candidate engine. Prioritize wick/absorption formation + confirmed range breakout as a distinct setup family. Keep it isolated from Engine 01 (Alpha trend flip) and Engine 02 (LuxAlgo market structure); combine only through the app's confluence/risk layer after parity tests.
