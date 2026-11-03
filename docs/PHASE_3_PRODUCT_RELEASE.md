# Phase 3 — Risk, Alerts and Trade Journal

## Included features

- Persistent risk profile stored in the same SQLite/PostgreSQL database as candle history.
- Risk checks for TP1 reward/risk, maximum trades per UTC day, maximum open trades, cooldown, optional stricter spread ceiling and daily loss once balance is configured.
- Position-size estimate only when account balance and exact broker contract size are entered.
- Durable BUY/SELL alert history. Events are created only after the server-side final 1H decision, authenticated fresh-data checks and broker spread gate pass. Same-direction repeated analyses are deduplicated; a WAIT or opposite signal resets the transition.
- Optional browser notifications. The user must explicitly grant browser permission.
- Manual trade journal with entry, stop, target, lot size, exit price and manually entered realized PnL.

## Dashboard

The Phase 2/P2.1–P2.6 acceptance tracker has been removed from the main dashboard. The repository's old Phase 2 research scripts remain available for engineering audit; they are not visible trading widgets.

Visible product sections include the 1H-primary Gold Report, Risk Management & Position Sizing, Alerts, Trade Journal, supply/demand zone radar and historical replay.

## API

- `GET /api/risk/settings`
- `PUT /api/risk/settings`
- `GET /api/alerts?limit=50`
- `GET /api/journal?limit=50`
- `POST /api/journal`
- `POST /api/journal/{id}/close`

The new database tables are initialized automatically and share the configured SQLite/PostgreSQL database. Existing data is not deleted.

## Default risk policy

Risk per trade defaults to 0.5%, maximum daily loss to 2%, maximum trades per day to 3, maximum open trades to 1, cooldown to 60 minutes and minimum TP1 reward/risk to 1.0. The default trade plan's first target is 1R; the TP1 gate therefore starts at 1.0R instead of silently blocking every default setup.

Account balance and contract size are blank by default. The daily-loss cap is enforced only when balance is supplied. Lot size is not estimated until both account balance and the exact broker contract size are supplied. The optional user spread cap can only tighten the existing server-configured spread gate.

## Boundaries

- Position sizing is a price-distance estimate. Confirm contract size, tick value, lot step, margin and account currency with the broker before using it.
- Journal entries are manual records; PnL is entered by the user and is not inferred from broker fills.
- No broker order is placed, modified or closed by the app.
- True market-by-order depth, aggressor-side CVD, open interest, trade prints and iceberg evidence still need a separately licensed, configured feed.
