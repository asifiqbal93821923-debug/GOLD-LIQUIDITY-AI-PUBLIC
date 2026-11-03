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
- [x] Verify Pages assets and data JSON return HTTP 200 after deployment (2026-11-03 deployment smoke test: root, snapshot JSON, and history JSON all HTTP 200; 474 points in each data file).
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


## Final verification evidence — 2026-11-03

- GitHub Actions on commit `5c30d494ab675efa65b5e9184b4a89c1f81c9989`: backend suite passed (78 tests), frontend CI/build passed, Docker build passed, and production API smoke test passed.
- Render service `gold-terminal-api`: latest deployment `dep-dbkue6c3a9gc73facbbg` is live; no error-level Render logs were returned during the audit.
- Production API reported `historical_store=postgresql`, `live_data=false`, and zero stored 1H candles. PostgreSQL connection/configuration and read endpoint are responding, but candle write/read/redeploy persistence is not yet proven.
- Public XAUS archive currently contains 474 sampled points spanning about 39.8 hours. The rolling 90-day retention logic passed its unit tests; 90 days of accumulated history is not present yet.
- Collector workflow is configured for every 15 minutes, but the four scheduled runs visible during this audit were 54–75 minutes apart. The required continuous 24-hour cadence/gap check has therefore not passed.
- GitHub Pages deployment `41649519098` succeeded after the workflow fix in commit `58589faf89cbdf5f58b8dd5612a228a206f2a110`; the post-deploy check confirmed the app root and both JSON data assets return HTTP 200, with 474 points and 90-day retention metadata.
- Frontend source review confirms archive → snapshot → direct public-feed fallback and rejection of stale/future samples. Backend tests cover stale/future broker candles/quotes and fail-closed spread gates. A dedicated browser-side controlled-fixture test for all-stale WAIT/no-signal remains outstanding.
- Android multi-browser reload, clean-profile, orientation/resize, and low-memory tests require a real Android browser session and remain outstanding.

MT5 Desktop/EA operation is excluded from this Phase 1 sign-off per the current setup; it is not counted as a remaining acceptance test.
