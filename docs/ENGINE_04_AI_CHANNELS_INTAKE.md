# Engine 04 — AI Channels (Clustering) Intake

## Source identity and license
- Indicator: AI Channels (Clustering) [LuxAlgo]
- Author: LuxAlgo
- Pine Script: v5
- License: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)
- Preserve LuxAlgo attribution and the complete license notice. Non-commercial and ShareAlike conditions apply to adaptations; do not treat this as proprietary/commercially redistributable code without separate permission.

## Intake status
- Complete source received in conversation.
- Status: reviewed and documented; not ported or parity-certified.
- Source settings: window 30, K=5 (3–10), denoise enabled, trailing-stop display disabled, max iterations 500, historical calculation limit 5000.

## Core algorithm
1. On eligible historical bars, collect the most recent `length` closing prices.
2. Initialize K centroids from linearly interpolated percentiles at integer percentages `int(i/(K+1)*100)`, for i=1..K.
3. Run K-means iterations: assign each close to its nearest absolute-distance centroid, then replace each centroid with its cluster mean.
4. The source's convergence check compares only centroids 0, 1 and 2, even when K > 3. This is a material source behavior/possible defect; do not silently "fix" it if exact parity is the goal. A corrected implementation should compare all K centroids and be versioned as an intentional improvement.
5. Channel anchors: upper = highest-index centroid; lower = lowest-index centroid; average = centroid at floor((K-1)/2). Upper/lower dispersion use the standard deviation of the corresponding extreme clusters.
6. Denoising uses a persistent state: close above upper sets bullish state; close below lower sets bearish state. In bullish state each output level is prevented from falling; in bearish state each is prevented from rising. Without denoise, raw levels are used.
7. Dispersion boundaries are upper minus upper-cluster standard deviation and lower plus lower-cluster standard deviation. Optional trailing-stop presentation hides one side depending on state; it does not change the clustering itself.

## Candidate app features (recommended)
- Adaptive price-distribution channel (upper / central cluster / lower).
- Extreme-cluster dispersion bands as an adaptive volatility/dispersion envelope.
- Price location: above upper, inside channel, below lower.
- Optional denoised/trailing channel state as a trend regime filter.
- Multi-timeframe channel context (recalculate on each target timeframe's own closes; do not resample already-computed values naively).

## Limitations and engineering risks
- K-means clusters price levels in a rolling close-price sample; it is not a regression channel, directional forecast, supply/demand zone, or evidence of institutional positioning.
- Cluster labels can be unstable if centroids are not sorted or clusters become empty. The Pine code assumes cluster ordering from percentile initialization and nearest-centroid assignment; a robust port must test ordering and empty-cluster behavior.
- The script calculates percentiles before validating that the data array has enough observations. Early-history and maxData edge cases need explicit handling.
- The convergence condition checks only the first three centroids, despite allowing K up to 10. Preserve for strict parity; separately test a corrected all-centroid convergence variant.
- maxIter loop uses `0 to maxIter`, so it may execute maxIter+1 passes in Pine. Verify exact loop semantics in parity tests.
- maxData limits which historical bars run clustering, but the script's persistent variables and last-bar-relative window can create historical/realtime differences. Validate replay, reload and realtime behavior.
- Exact floating-point equality is used for convergence. Consider tolerance-based convergence only in a separately versioned corrected engine.
- Standard deviation of empty/singleton clusters can be na; the source uses nz around centroid values but not all dispersion values. Define explicit data-quality behavior.
- This is computationally heavier than EMA/ATR bands. Cache or update only when a new bar closes; benchmark per symbol/timeframe and bound iterations.
- No volume, order-flow, BOS/CHoCH or explicit entry/SL/TP logic is present. It should be a context/regime engine, not a standalone trade trigger.

## Proposed normalized output
- engine_id: ai_channels_kmeans
- window_size, cluster_count, iterations_used
- upper_centroid, central_centroid, lower_centroid
- upper_dispersion, lower_dispersion
- upper_band_inner, lower_band_inner
- channel_state: bullish | bearish | neutral
- price_location: above | inside | below
- denoised: boolean
- trailing_stop_mode: boolean
- data_quality: warmup_incomplete | empty_cluster | valid
- implementation_variant: pine_parity | corrected

## Required tests
- Percentile initialization for K=3, 5 and 10.
- K-means assignment, tie behavior, centroid updates, empty clusters and centroid ordering.
- Convergence behavior for K>3 and maxIter boundaries.
- Standard deviation for empty/singleton/extreme clusters.
- Denoise state transitions and monotonic output behavior.
- maxData cutoff, early history, reload/replay determinism.
- Realtime closed-bar update behavior and no lookahead.
- Performance benchmark at 30/100/500 windows and K=3/5/10.
- Compare outputs to TradingView exports on identical OHLCV/close series and exact inputs.

## Integration decision
Accept as a separate context engine, not a signal engine. Use it to classify price location and channel regime alongside Alpha trend and SMC/WSB structure. Do not count channel position and denoised state as independent confirmations; they are derived from the same clustering model.
