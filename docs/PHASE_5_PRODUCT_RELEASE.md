# Phase 5 — Continuous MT5 Forward Paper Trading

Version: 0.7.0

## Purpose

Phase 5 is a forward-observation engine, not another historical backtest. It listens to the authenticated MT5 bridge, evaluates a newly closed 1H decision once, queues a risk-approved plan, and simulates an entry on the next 1H candle. The application never submits a market, pending, SL, or TP order to the broker.

## Operating sequence

1. The MT5 Expert Advisor uploads closed 4H, 1H, 15M and optional 5M candles.
2. The EA posts the current Bid/Ask quote to `POST /api/market/quote/bridge`. That authenticated quote update is the forward-cycle trigger.
3. The server verifies its own MT5 candle freshness, quote timestamp, server spread limit and Phase 5-specific spread ceiling. A stale or rejected feed does not start a cycle.
4. Only a new closed 1H candle is processed. A durable unique candle key prevents duplicate processing if the EA repeats a quote request or the API restarts.
5. The server builds the Gold Report with data no later than the decision candle's close. It uses 4H macro, 1H primary, 15M setup and optional 5M refinement.
6. A BUY/SELL signal must pass the existing risk manager and paper spread gate. The plan becomes a pending paper signal for the following 1H candle.
7. At the following 1H open, the engine simulates an entry only if that open lies inside the signal's original entry zone. A gap outside the zone expires the pending signal; the engine never chases.
8. Open paper trades are evaluated on subsequent fully closed 1H candles. Stop-first resolves an ambiguous bar in which both stop and TP1 were touched.
9. The paper event and trade lifecycle are durably stored. The status endpoint reports processed events, open/closed trades, win rate, net price PnL, average R, profit factor in R and max drawdown in R.

## Simulated execution policy

- Entry: next 1H bar open, only inside original 1H entry zone.
- Spread: actual current MT5 quote spread, with the configured point-size conversion.
- Slippage: explicit input in points per side.
- Commission: explicit input in points per side.
- Exit: full simulated position closes at Stop or TP1. TP2/TP3 are recorded as plan levels but are not partial-exit instructions in this Phase 5 version.
- Ambiguity: stop-first if stop and TP1 fall inside the same closed OHLC bar.
- No fill claim: OHLC data cannot reproduce the real tick path, latency, queue position or guaranteed broker fills.
- No execution API: no broker order is placed, modified or closed.

## Start gate

The engine is OFF by default. A start request is rejected unless all checks pass:

- A persistent ledger store is available. Use PostgreSQL on Render or a deliberately configured persistent disk; do not rely on Render's ephemeral SQLite filesystem.
- Server-side `MARKET_INGEST_TOKEN` is configured and matches the private EA input.
- Server-side `MAX_SPREAD_POINTS` is a measured, positive cap.
- Phase 5 `max_spread_points` is positive and no wider than the server cap.
- Fresh authenticated 4H, 1H and 15M MT5 closed candles are present, with at least 50 rows per timeframe.
- Fresh authenticated Bid/Ask quote is within both spread gates and has valid point size/time.
- The MT5 bridge's latest closed bars are not future-dated or stale under server freshness policy.

The dashboard status endpoint returns readiness blockers. A disabled engine does not start paper observation. The readiness gate must not be bypassed by an imported CSV or by browser-supplied freshness flags.

## Environment and setup

Set these variables privately on the API host:

- `MARKET_INGEST_TOKEN`: long random secret shared with the EA.
- `MAX_SPREAD_POINTS`: broker-observed maximum spread in that symbol's MT5 points.
- `DATABASE_URL`: durable PostgreSQL URL (recommended on Render). SQLite is intended for local development unless an explicitly persistent disk is attached and approved.
- `CORS_ORIGINS`: trusted dashboard origin(s), if different from the default.

In MT5 Desktop:

1. Confirm the broker's XAUUSD symbol or suffix (for example a broker-specific symbol name) and update `InpSymbol` if necessary.
2. Compile `mt5/GoldLiquidityBridge.mq5` in MetaEditor.
3. Set the API base URL and same private bridge token in EA inputs.
4. Add the API host to MT5 Tools → Options → Expert Advisors → Allow WebRequest.
5. Attach the EA to an open chart and confirm successful uploads for 4H, 1H, 15M, optional 5M and Bid/Ask.
6. Verify `/api/config/status` shows live fresh data and acceptable spread.
7. In the Phase 5 card, set the measured paper spread cap, slippage and commission, save, then use **Start forward paper**. A failed readiness gate should be fixed rather than bypassed.

## API reference

- `GET /api/paper-forward/status`
- `PUT /api/paper-forward/config`
- `GET /api/paper-forward/trades?limit=200`
- `GET /api/paper-forward/events?limit=100`

The config body contains `enabled`, `max_spread_points`, `slippage_points`, and `commission_points_per_side`. The server returns HTTP 409 if `enabled=true` is requested before all readiness checks pass.

## Verification and acceptance

Automated tests cover:
- Config validation and safe defaults.
- Persistent storage and duplicate event claims.
- Next-bar entry only inside the planned zone.
- No-chase expiry when the open misses the zone.
- Stop-first ambiguity resolution.
- Cost deductions and R-multiple performance calculation.
- Conversion of paper trades into a read-only risk-gate view.

Acceptance still requires real-world observation:
- Compile and attach the EA on the target broker's MT5 terminal.
- Verify correct symbol, server clock, candle boundaries, tick time and point size.
- Start the engine only after the server readiness report is green.
- Observe a declared period of future market sessions; record every event, duplicate, blocked signal, open/closed paper trade and feed interruption.
- Review enough trades for meaningful sample size, costs, expectancy, drawdown and risk-policy compliance.

No forward data or performance history is fabricated by the software. Phase 5 code tests passing does not mean the live observation period has started, completed or passed. Phase 5 is not strategy certification and does not guarantee profits.
