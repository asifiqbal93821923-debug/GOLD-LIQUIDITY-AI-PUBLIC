# Unified Gold Intelligence Engine — Feature Selection & Architecture

## Product objective
Build one XAUUSD analysis application from four independently testable source families. It should explain market condition and produce BUY, SELL or WAIT only after confirmed evidence and risk checks. The system is an analytical decision-support tool, not a promise of profit or a view into private institutional order books.

## Timeframe hierarchy
| Timeframe | Authority | Responsibilities |
|---|---|---|
| 4H | Macro context | Major trend, external swing range, major liquidity and prior-week/month levels |
| 1H | Primary decision timeframe | Main bias, swing structure, primary supply/demand and trade direction |
| 15m | Setup timeframe | Internal structure, retest, FVG/OB interaction and WSB formation |
| 5m | Execution confirmation | Trigger candle, local rejection and risk refinement |
| 3m | Optional display only | Never recalculates or moves 1H/4H master zones |

A lower timeframe may refine an entry but cannot independently reverse the 1H bias. All higher-timeframe inputs must be from completed bars for confirmed decisions.

## Source-family selection

### Engine 01 — Alpha Signal Engine Pro [MarkitTick]
**Keep:** adaptive ATR/dynamic-band trend state, trend flip, volatility regime, slope/stall context, range percentile, relative volume and breakout override as one trend/momentum family.

**Adapt:** separate raw source-parity output from production-safe output; guard warmup and missing volume; ensure confirmed-bar event semantics.

**Do not double count:** slope, trend direction, band position and breakout override are correlated parts of one engine.

**License:** source header is CC BY-NC-SA 4.0; preserve attribution and non-commercial/share-alike terms; commercial permission needed.

### Engine 02 — Smart Money Concepts [LuxAlgo]
**Keep:** confirmed swing/internal BOS/CHoCH, swing anchors, candle-derived OB, EQH/EQL, confirmed FVG, prior D/W/M levels, premium/discount and strong/weak swing context.

**Adapt:** 1H/4H anchors remain authoritative across 15m/5m/3m chart views; confirmed HTF data only; bounded arrays; safe reverse-index invalidation; freshness and mitigation state for zones.

**Do not double count:** swing and internal breaks for one event; OB/FVG/displacement from one impulse; EQH/EQL plus a sweep of the same pool.

**License:** LuxAlgo CC BY-NC-SA 4.0; commercial use requires separate permission.

### Engine 03 — Wick Sequence Breakout (WSB)
**Keep:** multi-candle wick formation, optional ATR range filter, absorption-style volume/range condition, formation boundaries, breakout direction, expiry and ATR/RR target scaffolding.

**Adapt:** label volume split as candle-location estimate only; use tick volume only as broker-specific activity proxy; return WAIT if both boundaries break ambiguously; conservative stop-first when OHLC cannot reveal TP/SL order.

**Do not double count:** wick shape, absorption and range expansion are one WSB setup family.

**License:** Mozilla Public License 2.0; retain required notices and comply with file-level copyleft requirements for modified MPL files.

### Engine 04 — AI Channels (Clustering) [LuxAlgo]
**Keep:** rolling close-price K-means clusters, upper/lower adaptive bands, center and denoised channel state as a context/regime family.

**Adapt:** handle empty clusters, sort centroids, check convergence across all K centroids, use bounded computation and explicit warmup. Preserve a source-parity variant separately from corrected behavior.

**Do not use as:** forecast, SMC zone, independent BUY/SELL signal or proof of institutional positioning.

**License:** LuxAlgo CC BY-NC-SA 4.0; commercial use requires separate permission.

## Unified analysis pipeline
1. **Data validation:** symbol, feed, timezone, OHLC integrity, candle-close state, spread and volume semantics.
2. **4H macro context:** confirmed swing direction, major range and external levels.
3. **1H primary context:** Alpha regime + SMC swing structure + AI channel context.
4. **15m setup:** SMC internal structure, zone/FVG interaction and WSB formation/breakout.
5. **5m trigger:** closed-candle confirmation, rejection/continuation and spread-aware entry.
6. **Confluence resolver:** combine evidence by family, suppress correlated duplicates, detect conflicts and require minimum independent families.
7. **Risk planner:** entry, invalidation, SL, TP1/TP2/TP3, R multiples, position sizing inputs and no-trade conditions.
8. **Explanation layer:** Bengali reason codes describing what aligned, what conflicted and what is still unconfirmed.

## Initial decision policy (to calibrate, not a performance claim)
- **BUY candidate:** 4H/1H bias bullish; 1H structure not invalidated; 15m bullish setup at a valid zone/liquidity context; 5m close confirms trigger; risk/reward and spread pass.
- **SELL candidate:** mirrored bearish conditions.
- **WAIT:** mixed HTF bias, unconfirmed break, no valid retest/trigger, stale/mitigated zone, insufficient independent evidence, high spread, missing data or ambiguous intrabar sequence.
- One lower-TF signal cannot override 1H/4H.
- Never issue a trade solely from AI Channels, one BOS/CHoCH label, one wick, or a single indicator score.

Weights and thresholds must be learned/calibrated only on separated in-sample data and evaluated on untouched out-of-sample/walk-forward periods. Do not invent a confidence percentage before calibration.

## Required app features from the original project discussion
- Real XAUUSD OHLC candles and historical/live feed; no runtime dependence on the TradingView app.
- Multi-timeframe selector with 1H primary and 4H macro confirmation.
- On-chart support/resistance, supply/demand, OB, FVG, EQH/EQL, liquidity sweep estimates and confirmed structure labels.
- Clear BUY/SELL/WAIT dashboard with entry, SL, TP1/TP2/TP3, RR and invalidation reason.
- Bengali explanations and alert/event history.
- Main-chart annotations only; clean chart without unnecessary BUY/SELL/BO/SWAP clutter.
- Stable 1H/4H zones when switching to 3m/5m.
- Backtest/replay, trade journal, spread/commission/slippage modelling and performance report.
- Responsive web/PWA first; Android package after feed and engine validation.

## Additional features recommended before live use
1. Data-source health panel: feed timestamp, candle delay, missing bars, broker symbol and tick-volume warning.
2. Economic-news/session guard for high-impact USD events and rollover/spread spikes; news must be a risk filter, not a directional oracle.
3. Zone lifecycle: created → fresh → tested → partially mitigated → invalidated/expired.
4. Signal lifecycle: forming → confirmed → active → invalidated/expired; prevent duplicate alerts.
5. Risk controls: max daily loss, max trades/day, cooldown, minimum RR, max spread and no-trade window.
6. Explainability: every decision shows exact timeframe, candle close time, evidence family and invalidation level.
7. Auditability: log engine versions, settings, feed, input candle IDs and decision output for reproducibility.
8. Security: keep provider/API credentials server-side; never embed secrets in Android/web client.

## Build and validation gates
- Gate A: receive source + license audit.
- Gate B: implement isolated modules and unit tests.
- Gate C: compare each module to TradingView-exported golden OHLCV fixtures with identical settings.
- Gate D: test no repaint/lookahead, realtime vs replay, MTF boundaries and missing data.
- Gate E: run walk-forward/out-of-sample tests with realistic costs and report drawdown, expectancy, profit factor, trade count and stability.
- Gate F: connect live feed only after previous gates pass; paper trade before any live use.
- Gate G: build PWA and Android package after stable web functionality.

## Current status
All four source families have been reviewed and their candidate roles selected. This document is an architecture/selection blueprint, not a completed integrated indicator. Alpha has an initial Python port; SMC, WSB and AI Channels are not yet fully ported and parity-certified. There is no production live feed, validated trade planner or Android APK yet.
