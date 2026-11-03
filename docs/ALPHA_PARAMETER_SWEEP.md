# Alpha Signal Parameter Sweep

This tool searches a reproducible sample of up to 500 Alpha Signal Engine parameter combinations for the causal 4H/1H/15M/optional-5M Gold Report replay.

## Method

- Inputs swept: all 21 exposed Alpha settings, including ATR/band/weight values, EMA smoothing, volatility fingerprint, stall/slope/volume/range/BPS filters, lookbacks, thresholds and breakout override. The first candidates are one-factor-at-a-time tests; remaining slots are deterministic multi-factor combinations.
- Default request: 100 candidates. The seed is fixed by default, so the same input produces the same candidates.
- Chronological split: 60% train, 20% validation, 20% sealed test.
- Every train, validation and test partition must independently contain at least 50 closed candles in 4H, 1H and 15M. Bars that straddle a split boundary are excluded.
- Candidate selection uses train and validation only. It rejects candidates with fewer than the configured minimum trades (default 10) in either window or non-positive net PnL in either window.
- Ranking uses the weaker of train and validation average-R, profit factor, win rate and drawdown ratio. Win rate alone is not the objective.
- The sealed test is evaluated once for the selected candidate, not searched for a second winner.

## Input format

Provide JSON with chronological OHLCV rows, oldest first:

```json
{
  "4h": [{"time": 0, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}],
  "1h": [],
  "15m": [],
  "5m": []
}
```

Timestamps are Unix seconds at candle open. Use the same XAUUSD broker/feed for every timeframe and export fully closed candles. Do not substitute spot samples or invented volume for broker candles.

## Run

```bash
python scripts/optimize_alpha_settings.py \
  --input xau_mtf_ohlcv.json \
  --candidates 100 \
  --spread-points 25 \
  --slippage-points 5 \
  --commission-points-per-side 0 \
  --point-size 0.01 \
  --output optimization-report.json
```

Replace costs with the real target broker's XAUUSD contract assumptions. Those example costs are placeholders, not a recommendation.

## Limits

The tool is a parameter-sweep research harness, not proof of future performance, not certified Pine parity, and not an automatic live-trading authorization. At least 50 candles per timeframe per partition is a technical minimum, not a statistically sufficient sample. Re-test on multiple unseen market regimes and paper-trade before considering live use.
