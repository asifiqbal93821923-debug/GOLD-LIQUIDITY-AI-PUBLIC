# Phase 1 — Stability & Data Foundation

Status: implementation hardening committed; automated and device-level verification tracked separately.

## Scope and acceptance criteria

- [x] Dashboard JavaScript error boundary shows a useful fallback instead of a blank screen.
- [x] Retire the legacy service worker and delete old `gold-terminal-*` shell caches.
- [x] Chart setup handles browsers without `ResizeObserver` and guards initialization errors.
- [x] Free public data is explicitly labelled indicative/sample data, not broker ticks or execution data.
- [x] Free-feed loader tries scheduled archive, scheduled snapshot, then direct XAUS; validates each candidate's latest sample before choosing it.
- [x] Stale/future data is rejected; duplicate timestamps are collapsed and non-finite/non-positive prices are rejected.
- [x] Collector rejects stale/future latest samples and records source limitations in JSON metadata.
- [x] Collector retains a rolling 90-day archive as data accumulates.
- [ ] Verify repeated open/reload on multiple Android browsers and a clean browser profile.
- [ ] Verify scheduled collector for at least 24 hours; check run gaps and archive growth.
- [ ] Verify stale-source fallback using controlled fixtures and verify WAIT/no-signal behaviour when all sources are stale.
- [ ] Verify Pages assets and data JSON return HTTP 200 after deployment.
- [ ] Verify mobile chart resize/orientation changes and low-memory reload behaviour.

## Data integrity rules

1. Source priority: fresh scheduled archive -> fresh scheduled snapshot -> fresh direct public API.
2. Reject a candidate if it has fewer than 3 valid samples, a non-finite/non-positive price, or a latest timestamp in the future / older than 15 minutes.
3. Deduplicate equal timestamps; sort ascending before aggregation.
4. Aggregate sampled prices into indicative OHLC bars only. These are not true traded OHLCV; volume is not measured.
5. If no fresh source is available, show an error/no-data state. Never silently reuse stale data as live.
6. XAUS public endpoint is not XM Bid/Ask and cannot validate broker execution spread or institutional order flow.

## Operational checks

- Collector workflow: `.github/workflows/free-xau-data.yml` (15-minute schedule).
- Pages workflow: `.github/workflows/deploy-pages.yml`.
- CI and backend tests: repository Actions.
- Data files: `web/public/data/market-snapshot.json` and `web/public/data/market-history.json`.

## Explicitly out of Phase 1

MT5 desktop bridge operation, production FastAPI hosting, Pine parity, strategy profitability, real order-book/MBO access, broker execution and native APK packaging.
