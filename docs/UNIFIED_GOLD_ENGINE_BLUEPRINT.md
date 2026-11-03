# Unified Gold Intelligence Engine — Integration Blueprint

## Purpose
Create one explainable XAUUSD analysis system from the four user-submitted indicator families. This is an architecture and feature-selection specification, not a claim that the combined engine is already implemented or profitable.

Primary timeframe hierarchy:
- 4H: macro structure and major supply/demand context.
- 1H: primary directional bias and dealing range (the user's main decision timeframe).
- 15M: setup development, BOS/CHoCH confirmation, liquidity sweep/reclaim and zone reaction.
- 5M: precise entry trigger only after higher-timeframe alignment.
- Optional 1D: major reference levels and broader context.

All calculations must use standard OHLCV candles with explicit timezone/session and volume provenance. Signals default to closed-candle confirmation. No lookahead, repainting, or backdated signal timestamps.

## Source inventory and integration decisions

| Source | Source role | Keep/adapt | Do not treat as |
|---|---|---|---|
| Alpha Signal Engine Pro (MarkitTick, Pine v6, CC BY-NC-SA 4.0) | Trend, volatility and momentum regime | Recursive trend state, ATR/volatility fingerprint, slope/stall, candle range and volume filters, confirmed direction flips | Complete trade planner or S/R engine |
| Smart Money Concepts [LuxAlgo] (Pine v5, CC BY-NC-SA 4.0; partial source received) | Structure and liquidity context | Candidate swing/internal structure, BOS/CHoCH, candle-derived OB, EQH/EQL, FVG, HTF levels, premium/discount | Verified institutional orders or complete implementation until remaining source is supplied |
| Wick Sequence Breakout (Uncle_the_shooter, Pine v6, MPL-2.0) | Rejection/absorption and breakout setup | Wick sequence, high-volume/low-range absorption candidate, formation range, breakout/retest and optional ATR/RR risk references | True bid/ask delta, footprint or actual buyer/seller volume |
| AI Channels (Clustering) [LuxAlgo] (Pine v5, CC BY-NC-SA 4.0) | Adaptive distribution/channel regime | Upper/central/lower clusters, dispersion envelope, price location, denoised regime | Forecast, supply/demand zone or standalone entry signal |

### Source-specific defects and controls
- Alpha: current Python port is initial only. Preserve Pine warm-up, prior-bar offsets, percentile ranks and recursive state; parity is not certified.
- SMC: received source is incomplete. Remaining source is required to audit pivot confirmation, OB creation/mitigation, EQH/EQL matching, FVG, MTF calls and alert timing. Do not reconstruct missing proprietary logic by guesswork.
- WSB: estimated bull/bear pressure is close-location volume allocation, not true buy/sell volume. If volume is absent/unreliable, disable absorption/pressure filters. If a bar ambiguously breaks both formation boundaries, return WAIT. Same-bar SL/TP collisions require conservative handling or lower-timeframe data.
- AI Channels: Pine convergence checks only first three centroids although K can exceed three; empty clusters/dispersion and loop boundary need tests. Keep a pine_parity variant separate from any corrected all-centroid implementation. Use as context only.

## Unified architecture

1. **Market Data Adapter**
   - One normalized XAUUSD OHLCV candle schema, UTC timestamps plus display timezone.
   - Historical backfill and live stream, duplicate/out-of-order candle protection, gap detection.
   - Record provider, symbol mapping, spread, volume type (tick/real/unknown) and data freshness.
   - Never fabricate candles or expose API keys in the browser.

2. **Timeframe Aggregator**
   - Build/validate 5M, 15M, 1H, 4H and optional 1D candles from a consistent source where possible.
   - Only expose a higher-timeframe candle to lower-timeframe logic after its close.
   - No mixing candle boundaries from different feeds without explicit reconciliation.

3. **Isolated Feature Engines**
   - alpha_trend: direction, trend strength, ATR/volatility regime, slope, stall and flip.
   - smc_structure: confirmed swings, BOS/CHoCH, EQH/EQL, OB/FVG, premium/discount and HTF levels (blocked from full port until source complete).
   - wsb_setup: wick rejection sequence, absorption candidate, formation range, breakout/retest and expiry.
   - ai_channel_context: cluster levels, dispersion, channel location and denoised state.
   - Each module returns facts, timestamps, warm-up/data-quality flags and source/license metadata, not UI drawings.

4. **Institutional-Style Context Layer (price-action proxies only)**
   - Sweep-and-reclaim around confirmed equal highs/lows or prior session/day/week extremes.
   - Displacement candle after a sweep or structure break.
   - FVG/imbalance overlap and retest.
   - Supply/demand candidate from origin candle plus displacement, with freshness, mitigation and invalidation.
   - Premium/discount relative to a clearly defined 1H/4H dealing range.
   - Explicitly label these as candle-derived proxies, never verified bank orders or institutional positions.

5. **Confluence and Decision Engine**
   - Determine 4H macro bias, then 1H primary bias.
   - 15M qualifies the setup; 5M times the entry.
   - Independent evidence groups: (A) trend/regime, (B) structure/liquidity, (C) setup/trigger, (D) risk/data quality.
   - Do not count correlated values twice: Alpha flip + Alpha slope are one trend family; AI channel location + denoised state are one channel family; WSB wick + absorption + volume split are one setup family; internal and swing breaks from the same event are not two independent votes.
   - Hard vetoes: incomplete candle, stale/missing data, ambiguous dual breakout, invalidated zone, no valid stop, excessive spread, conflicting HTF bias unless explicitly in reversal mode.
   - Output BUY / SELL only when higher-timeframe context, structure, entry trigger and risk agree. Otherwise WAIT with reason codes.
   - Confidence is a transparent score of evidence and data quality, not a probability of profit.

6. **Trade Planner and Risk Engine**
   - Entry zone from confirmed retest/rejection, not arbitrary current price.
   - SL beyond structural invalidation with ATR buffer and minimum/maximum risk-distance checks.
   - TP1/TP2/TP3 from next opposing structure/liquidity levels, with RR fallback only when no reliable level exists.
   - Return RR per target, position-risk estimate only if account size/risk input is explicitly configured, and invalidate the plan when the premise fails.
   - No broker order execution in initial release.

7. **Explanation and Dashboard**
   - Bengali-first explanation: trend, structure, liquidity event, setup trigger, invalidation, risk and why WAIT.
   - Chart-only overlays: confirmed swings, BOS/CHoCH, zones, FVG, sweep markers, entry/SL/TP. No lower indicator pane.
   - Controls for timeframe, engine visibility, sensitivity and alert preferences.
   - Show source and volume quality; never label estimated pressure as real buy/sell volume.

## Feature selection: initial priority

### P0 — Required for a meaningful first unified release
1. Normalized XAUUSD data feed and reliable historical candles.
2. 4H + 1H bias with 15M setup and 5M entry confirmation.
3. Alpha trend/ATR regime (after parity tests).
4. Confirmed swing structure and close-based BOS/CHoCH (after full SMC source audit).
5. Sweep-and-reclaim around prior highs/lows and EQH/EQL.
6. Supply/demand candidate zones with origin, freshness, mitigation and invalidation.
7. WSB wick sequence + confirmed range breakout/retest (after parity tests).
8. WAIT-first confluence and structural SL/TP planner.
9. Bengali explanation and chart overlays.

### P1 — Add after P0 is stable
- FVG and displacement scoring.
- AI Channels as range/trend context filter after K-means edge-case and parity tests.
- Session windows (London/New York/overlap) with timezone/DST-safe configuration.
- Spread-aware trade eligibility and economic-calendar high-impact event warning.
- Previous day/week high-low and daily open.
- Alerts and setup expiry.

### P2 — Later enhancements
- True bid/ask delta, footprint or volume-at-price only if a suitable licensed feed is acquired.
- Walk-forward optimization and regime-specific statistics.
- Paper-trading journal, signal outcome analytics and calibrated confidence.
- Android packaging after web/data/analysis core is stable.

## Additional requirements from the original project discussions
- Professional supply/demand blueprint focused on 1H main chart and 4H confirmation.
- Three-part institutional-style confluence: liquidity sweep/reclaim + displacement/momentum + imbalance/FVG/zone retest. These are observable price-action proxies, not institutional order-book data.
- BUY/SELL/WAIT, entry, SL, TP1/TP2/TP3, confirmation status and plain Bengali reason.
- 5M/15M/1H/4H/1D chart timeframes; chart annotations only.
- Live/historical feed, not a TradingView runtime dependency.
- Validate against identical TradingView-exported OHLCV fixtures; then replay, walk-forward, out-of-sample and paper test with spread/commission/slippage.
- Web first, Android later; no order execution in the first release.

## Validation gates before enabling signals
1. Complete-source and license audit for every adapted engine.
2. Unit tests for edge cases, warm-up, missing volume, MTF alignment and candle-close semantics.
3. Golden fixture comparison against TradingView for identical OHLCV, timeframe and inputs.
4. No-lookahead/replay/reload determinism tests.
5. Historical replay, walk-forward and out-of-sample tests.
6. Spread, commission, slippage and session sensitivity.
7. Paper trading and monitoring before any live reliance.

A passing build is not proof of profitability. Do not advertise a win rate until independently measured on out-of-sample data.

## Current implementation status
- Source intake documentation exists for Engines 01–04.
- Engine 01 has an initial Python/API port and basic tests; parity is pending.
- Engines 02–04 are documented but not ported/parity-certified.
- Engine 02 cannot be fully audited because the supplied source text is partial.
- Production feed, unified confluence, trade planner, completed dashboard and Android package are not complete.