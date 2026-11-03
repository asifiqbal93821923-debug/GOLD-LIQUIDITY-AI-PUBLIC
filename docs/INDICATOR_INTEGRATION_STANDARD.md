# Indicator Integration Standard

## Purpose
Combine multiple user-supplied Pine Script indicators into one independent XAUUSD analysis engine without blindly stacking signals.

## Intake and licensing gate
For every submitted source, record:
- Indicator name, original author, source URL (if supplied), version and exact license header.
- Inputs/defaults, timeframe assumptions, required data (OHLCV, tick volume, bid/ask, trades).
- Repainting/look-ahead risks, bar-close behavior, and any external dependencies.
- What the source genuinely calculates versus what its marketing description suggests.

Do not merge code until its license permits the intended use. Preserve attribution and all required notices. If a source is non-commercial/share-alike, keep derivative distribution within those terms; obtain separate permission before any commercial use.

## Feature extraction rubric
Score each candidate feature from 0–5 on:
1. Objective definition and reproducibility.
2. No-lookahead / closed-candle reliability.
3. Relevance to XAUUSD across 5m, 15m, 1h and 4h.
4. Incremental value beyond features already implemented.
5. Testability against historical candles.
6. Runtime cost and explainability.

Prioritize features that add independent information:
- Trend and regime: direction, slope, volatility regime, trend exhaustion.
- Structure: confirmed swing highs/lows, BOS/CHOCH with explicit confirmation.
- Liquidity: equal highs/lows, sweep-and-reclaim, displacement after sweep.
- Zones: origin candle plus displacement, freshness, mitigation and invalidation.
- Momentum/participation: candle body/range, ATR expansion, volume/tick-volume context.
- Trade planning: entry trigger, invalidation, stop distance, staged targets and R-multiple.

Do not describe candle-derived estimates as real bank orders, order-book depth, or institutional positions. True footprint requires suitable trade/volume-at-price data.

## Engine architecture
Keep each source-derived calculation in an isolated module with:
- normalized input schema and explicit settings,
- deterministic output schema,
- source attribution and license metadata,
- unit tests and parity fixtures,
- a feature capability declaration.

A separate confluence layer combines outputs. It must avoid double-counting correlated indicators. A trade plan is emitted only when direction, structure, trigger and risk constraints agree; otherwise return WAIT with reasons.

## Standard output
Each engine should return:
- status, engine_id, source_attribution, license,
- symbol, timeframe, candle_timestamp, confirmed_bar,
- direction/regime, signal, confidence_components,
- feature values and filter states,
- invalidation/reason codes and warnings.

The combined planner should return entry_zone, stop_loss, targets [TP1, TP2, TP3], risk_reward, confirmation_state, and explanation. Null values are preferable to invented levels.

## Validation gates
1. Unit tests for edge cases and missing data.
2. Golden-fixture parity against TradingView exports using identical OHLCV, timeframe, settings and standard candles.
3. Historical replay with no future data leakage.
4. Walk-forward and out-of-sample testing.
5. Spread, commission, slippage and session sensitivity.
6. Paper trading before any live reliance.

A passing build or unit test is not evidence of profitability. No live execution is enabled in the initial app.
