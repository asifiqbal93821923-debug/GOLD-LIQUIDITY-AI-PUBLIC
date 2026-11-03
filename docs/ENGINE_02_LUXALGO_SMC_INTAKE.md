# Engine 02 — LuxAlgo Smart Money Concepts (Source Intake)

## Intake status
- Indicator: Smart Money Concepts [LuxAlgo]
- Original author: LuxAlgo
- Pine version: v5
- License header supplied by user: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)
- Source status: PARTIAL. The received text ends during the variable declarations at `varip int lastBarIndex`; calculation and execution sections are missing. This is an intake inventory only, not a verified port.
- Required handling: preserve LuxAlgo attribution and license notice. Do not use commercially unless separate permission is obtained. Any derivative distributed from this source must comply with CC BY-NC-SA 4.0.

## Feature inventory visible in the submitted source

| Feature | What it can contribute | Initial decision |
|---|---|---|
| Swing market structure | Confirmed swing highs/lows and major structure breaks | Core candidate |
| Internal market structure | Faster, more sensitive structure shifts | Candidate; filter noise |
| BOS | Continuation break of a prior structure level | Core candidate |
| CHoCH | Potential change in directional structure | Core candidate; require close/confirmation |
| Internal and swing trend bias | Separate short-term and major structure direction | Core candidate |
| Internal and swing order blocks | Candle-origin zones associated with structure moves | Candidate; validate exact creation/mitigation rules from full source |
| Equal highs / equal lows | Potential liquidity pools | Core candidate |
| Fair Value Gaps | Three-candle imbalance zones, optionally on another timeframe | Core candidate; validate threshold and mitigation rules |
| Strong / weak highs and lows | Context for likely protected vs vulnerable extremes | Candidate; treat as heuristic |
| Daily / weekly / monthly highs and lows | Higher-timeframe reference levels | Core candidate |
| Premium / discount / equilibrium | Position within the current dealing range | Core candidate |
| Trend-colored candles | Visual summary of structure bias | Optional display only |

## Important implementation notes
- Pivot-based swing points are only known after their right-side confirmation bars have elapsed. The app must timestamp the actual pivot candle separately from the later confirmation candle; never backdate a signal as if it were known earlier.
- BOS/CHoCH must be calculated from confirmed levels and a documented break rule (close or wick). The user-visible trade trigger should default to closed-candle confirmation.
- Order blocks are price-action-derived zones in this script, not verified resting institutional orders or bank order-book positions.
- Equal highs/lows are candidate liquidity pools, not proof that stops exist at that price.
- FVG is a candle-price imbalance, not proof of unfilled institutional orders.
- MTF FVG and HTF levels require correct timeframe alignment, timezone handling and no future-bar leakage.
- Internal structure is expected to be noisier than swing structure. Do not count both as two independent confirmations when they describe the same break.
- Premium/discount depends on the selected dealing range. The exact range update rules must be recovered from the complete source.

## Proposed role in the combined app
Use this as the Market Structure and Liquidity Context engine, complementary to Engine 01 (Alpha Signal Engine Pro):
1. Engine 01 provides trend/direction regime and flip signal.
2. Engine 02 provides structure context: swing/internal BOS/CHoCH, EQH/EQL, OB/FVG zones and HTF levels.
3. A separate confluence/risk planner decides BUY / SELL / WAIT. It must not issue a trade merely because one structure label appeared.
4. Entry, SL and TP must be calculated by a separate tested risk module; they are not claimed as supplied by this source.

## Work still blocked
The remaining Pine source is required before implementing and validating:
- pivot/leg detection and structure-break execution logic,
- exact order-block parsing, filtering and mitigation,
- equal-high/low matching and confirmation,
- FVG detection, auto threshold, MTF request and invalidation,
- trailing strong/weak extremes,
- premium/discount range calculations,
- alerts and bar confirmation behavior.

## Validation checklist
- Port only after the complete source is received.
- Build golden fixtures from identical standard OHLCV/timeframe/settings and compare against TradingView exports.
- Test pivot confirmation delay, bar-close vs wick breaks, MTF alignment, zone invalidation, missing volume, session gaps and replay for look-ahead.
- Do not claim profitability or real institutional order visibility.
