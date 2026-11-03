# Gold Terminal — Phase 2 dashboard guide

The dashboard's **Research Completion Tracker** is an evidence-readiness view, not a claim that the research phase has passed.

## What the six rows mean

- **P2.1 Historical data:** counts already imported into the app are displayed for 4H, 1H and 15M. Planning floors (250 / 1,000 / 4,000 bars) are not statistical guarantees. The same provider and exact XAUUSD ticker, overlapping time range, fully closed candles, timestamp semantics, duplicate and gap checks are still required.
- **P2.2 Pine parity:** the comparator and metadata safeguards are code. The exact Alpha Pine source, all Inputs, confirmed-bar 1H export and candle-by-candle comparison report are evidence requirements. Other Pine scripts are not certified by Alpha.
- **P2.3 Calibration:** optimizer and trade-plan calibration code exist. Results must be generated from the accepted dataset and a non-zero maximum-spread cap.
- **P2.4 Walk-forward/OOS:** rolling folds and a sealed holdout are implemented. A reproducible report on the accepted dataset is still required.
- **P2.5 Execution costs:** cost scenarios and fail-closed spread controls exist. Confirm the target account's contract size, point value, commission, observed Bid/Ask spread and slippage before describing results as broker-calibrated.
- **P2.6 Paper forward:** the offline closed-candle ledger is not a live receiver. A persistent feed, durable logs and a predeclared forward observation period are required for acceptance.

## Independent data

The Dukascopy action produces an independent BID research dataset. Keep it under data/dukascopy_research/. Do not move it into data/phase2/, label it as TradingView data, or use it as XM360 Ask/Bid execution evidence. It can be used for a separate research report with source and limitations shown.

## Same-feed research inputs

The strict same-feed workflow expects:
- data/phase2/xauusd_4h.csv
- data/phase2/xauusd_1h.csv
- data/phase2/xauusd_15m.csv

For Pine parity it additionally expects:
- data/phase2/pine_reference_1h.csv
- data/phase2/pine-reference-meta.json
- data/phase2/alpha-settings.json

For observed XM360 quote audit it can consume data/phase2/xm360_quotes.csv with documented rollover inputs. Do not use assumed or example values as broker evidence.

**Phase 2 can only be marked ACCEPTED after the underlying empirical reports and forward observation satisfy their gates.**
