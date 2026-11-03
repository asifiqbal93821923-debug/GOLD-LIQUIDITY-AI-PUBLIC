# P2.6 — Forward / paper validation guide

P2.6 is a paper-only gate. It does not connect to XM360, MT5 or any broker and never sends orders.

## Event input

Prepare a JSONL file (one JSON object per line) at data/phase2/paper_forward_events.jsonl. Each record must contain:

- decision: the validated decision object, with decision BUY / SELL / WAIT and its timestamp.
- candle: the next fully closed 1H candle with Unix close timestamp, is_closed=true, and open/high/low/close.
- costs: spread_price, slippage_price, commission_price_per_side, and max_spread_price.

The candle must be closed and chronological. Forming, duplicate, old, malformed OHLC, or decision timestamps later than candle close are rejected. Costs must be finite and non-negative. A missing/zero maximum spread fails closed for new entries; existing open paper trades continue to be managed.

## Run locally

    python -m scripts.paper_forward_monitor --input data/phase2/paper_forward_events.jsonl --ledger data/paper-trades.json --audit reports/phase2/paper-forward-audit.jsonl

The monitor writes JSON and CSV trade ledgers, a per-event audit JSONL, and a summary JSON. It refuses to overwrite a corrupt existing ledger. The same workflow is available as a manual GitHub Actions run named "Phase 2.6 paper-forward audit".

## What the report can and cannot prove

The report counts opened/closed paper trades, WAIT decisions, spread-gate waits and rejected events. It enforces closed-candle chronology and explicit costs. This is deterministic offline replay of supplied events, not an always-on market feed. OHLC cannot reconstruct intrabar path or guaranteed fills.

## Release gate

P2.6 cannot be accepted until P2.1–P2.5 empirical blockers are resolved, a continuous paper-forward period is collected from a verified feed, signal/decision logs are reviewed for missed/duplicate/invalidated events, and risk/performance thresholds are agreed and met. No Phase 2 broker order execution is permitted.
