# Engine 02 — LuxAlgo Smart Money Concepts (Complete Source Audit)

## Intake status
- Indicator: Smart Money Concepts [LuxAlgo]
- Original author: LuxAlgo
- Pine version: v5
- Supplied license: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0), https://creativecommons.org/licenses/by-nc-sa/4.0/
- Source status: COMPLETE for the pasted indicator. The user supplied the full source through execution and alert conditions.
- Audit status: logic reviewed at source level; not yet ported, compiled in Pine, or parity-tested against TradingView exports.
- License gate: preserve attribution and license notice. CC BY-NC-SA is non-commercial; obtain separate permission before commercial use. Review share-alike obligations before distributing an adapted derivative.

## What the engine does
The source maintains separate internal and swing pivots/trend biases, detects structure breaks, optionally stores candle-derived order-block zones, detects equal highs/lows, creates and invalidates fair-value-gap zones, tracks trailing swing extremes, and can display prior daily/weekly/monthly levels and premium/discount/equilibrium regions.

### Feature selection for the unified XAUUSD app

| Feature | Proposed use | Decision |
|---|---|---|
| Swing pivots and swing trend | 1H/4H directional market structure | Adopt; pivot confirmation timestamp must be explicit |
| Swing BOS / CHoCH | Major continuation / possible reversal evidence | Adopt; use closed-bar break as default |
| Internal BOS / CHoCH | 15m/5m execution context | Adopt as secondary evidence; never equal-weight with swing break |
| Internal/swing order blocks | Candidate reaction zones from displacement-origin candles | Adapt; freshness, age, mitigation and invalidation tracking required |
| EQH / EQL | Candidate liquidity pools | Adopt; cluster nearby levels by ATR/tick tolerance |
| FVG | Imbalance zone and retracement context | Adopt; confirmed HTF values only |
| Strong/weak highs and lows | Vulnerability/context of current extremes | Adopt as heuristic, not certainty |
| Daily/weekly/monthly highs/lows | External liquidity and target references | Adopt; use prior completed periods |
| Premium/discount/equilibrium | Position within a defined dealing range | Adopt; define range from confirmed 1H/4H swing anchors |
| Trend-colored candles and visual labels | Chart decoration | Do not use in decision scoring |

## Source-level defects and adaptation requirements
1. **MTF FVG repaint risk:** `drawFairValueGaps()` calls `request.security(..., lookahead_on)` while requesting current HTF high/low/time fields. The port must only publish a gap after its source timeframe candle is confirmed, or use a rigorously shifted confirmed-bar expression. Do not copy this request pattern blindly.
2. **Array removal while iterating:** `deleteOrderBlocks()` and `deleteFairValueGaps()` remove elements from arrays during forward iteration. Depending on Pine iteration semantics this can skip adjacent invalidated entries. Port with reverse-index removal or a filtered rebuild and test multiple simultaneous invalidations.
3. **Unbounded history arrays:** `parsedHighs`, `parsedLows`, `highs`, `lows`, and `times` grow on every bar. The app implementation needs bounded retention or ring buffers without breaking index-to-time alignment.
4. **Pivot confirmation delay:** pivots are detected using an offset `size`; the pivot candle and the later confirmation candle are different. Store both timestamps. Never display a historical pivot as a signal that was available on the pivot candle.
5. **Order-block meaning:** these are candle-derived price zones around selected parsed highs/lows. They are not actual bank orders, resting liquidity, or verified institutional footprints.
6. **Equal highs/lows meaning:** EQH/EQL are approximate clustered extremes; they indicate possible liquidity concentration, not proof of stop orders.
7. **FVG threshold and MTF alignment:** reproduce the source calculation only in a parity mode, then separately test a corrected confirmed-HTF mode. Do not silently mix source parity and safer behavior.
8. **Volatility parsing:** large-range candles are parsed with high/low swapped for OB selection. Test zero/NA ATR warmup and sparse history.
9. **Trailing range initialization:** trailing extremes can be NA until valid swing pivots arrive. Guard all range, premium/discount and strong/weak calculations until both anchors are valid.
10. **Chart timeframe assumptions:** swing length is 50 and internal length is fixed at 5 in the supplied execution block. The unified app should use explicit timeframe profiles rather than letting a 3m chart redefine the primary 1H/4H structure.
11. **Alerts are event flags:** map alert booleans to one-bar events and ensure they do not persist or duplicate across realtime recalculations.
12. **License and attribution:** preserve LuxAlgo credit and CC BY-NC-SA notice in any derivative implementation and distribution. Commercial deployment needs separate licensing advice/permission.

## Recommended timeframe architecture
- **4H:** macro structure, major swing highs/lows, prior-week/month levels and broad dealing range.
- **1H (primary):** authoritative trend/structure bias, swing BOS/CHoCH, main supply/demand and liquidity context.
- **15m:** setup formation, internal structure shift, FVG/OB retest and WSB sequence.
- **5m:** optional execution confirmation only; must not override 1H/4H bias by itself.
- **3m:** visualization/execution detail only. It must never recalculate or relocate the master 1H/4H zones.

All MTF data must be aligned by candle close time, use completed higher-timeframe bars for confirmed decisions, and carry source timeframe + confirmation timestamp.

## Combined-engine role
This is the **Structure & Liquidity Context engine**, not a standalone BUY/SELL engine:
- Alpha Signal Engine: trend/regime and momentum transition.
- SMC: structure, BOS/CHoCH, candidate OB/FVG, EQH/EQL and HTF levels.
- WSB: wick-sequence/absorption-style formation and breakout evidence.
- AI Channels: adaptive price-cluster channel and regime context.
- Confluence/risk planner: resolves agreement/conflict, creates WAIT when evidence is weak, and calculates entry/SL/TP separately.

Avoid double counting: swing BOS + internal BOS for the same break are one structural family; OB + FVG + displacement from the same impulse are related evidence; WSB wick/volume/range subconditions are one setup family; AI channel position and its denoised state are one context family.

## Validation required before production
- Golden OHLCV fixtures exported from TradingView with exact symbol, timeframe, settings and timezone.
- Compare pivot events, BOS/CHoCH events, OB bounds/mitigation, EQH/EQL, FVG creation/invalidation, prior-period levels and premium/discount values.
- Test no-lookahead on 4H→1H→15m→5m, realtime/replay consistency, gaps/session boundaries, missing volume, NA warmup, and multiple zone invalidations on one bar.
- Include a separate corrected mode for repaint/array/retention fixes; document intentional differences from original LuxAlgo output.
- Do not claim profitability or actual institutional order-flow visibility.
