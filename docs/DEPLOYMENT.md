# Deployment (Docker Compose)

## Local/server deployment

1. Install Docker Engine and the Docker Compose plugin.
2. Copy `.env.example` to `.env`.
3. Replace `MARKET_INGEST_TOKEN` with a private random secret (32+ characters).
4. Keep `MAX_SPREAD_POINTS=0` until you have measured your broker's normal XAUUSD spread and chosen a risk-appropriate maximum.
5. Start the services:

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f api web
```

6. Open `http://localhost:8080`. API requests are reverse-proxied to FastAPI; SQLite candle data persists in the `candle_data` volume.
7. Configure the MT5 EA with base URL `http://YOUR_SERVER:8080` and the same bridge token. Add that host to MT5's WebRequest allow-list.

## Production hardening

- Put the web service behind HTTPS (reverse proxy/load balancer) before exposing it publicly.
- Restrict network access to the app and rotate the MT5 bridge token if exposed.
- Back up the `candle_data` volume.
- Set `MAX_SPREAD_POINTS` only after checking the broker's symbol digits, point size and typical session spreads. Until configured above zero and fresh quotes arrive, BUY/SELL decisions remain blocked by the spread gate.
- Configure monitoring, log retention, backups and a persistent host volume.
- No API key or token belongs in the frontend bundle or Git repository.

## Current deployment boundary

Docker packaging files are provided, but no cloud account, DNS, TLS certificate, VPS or production host has been configured by this repository change. A production deployment is therefore not claimed complete.


## GitHub Pages + separate API host (GOLD TERMINAL)

GitHub Pages serves only the static React/PWA frontend; it does not run FastAPI. To make dashboard API features work from the Pages URL:

1. Deploy **this repository's** FastAPI service to a persistent HTTPS host. Do not point it at the separate GOLD-LIQUIDITY-AI service.
2. In the GitHub repository settings, add an Actions repository variable named `GOLD_TERMINAL_API_BASE_URL` with the API origin only, for example `https://your-gold-terminal-api.example.com` (no trailing slash and no `/api` suffix).
3. On the API host, set `CORS_ORIGINS=https://asifiqbal93821923-debug.github.io` (include any additional trusted frontend origins only if needed), `MARKET_INGEST_TOKEN`, `CANDLE_DB_PATH`, and a measured `MAX_SPREAD_POINTS`.
4. Push a frontend change or manually run the **Deploy Android PWA to GitHub Pages** workflow so the frontend is rebuilt with the API origin.
5. Verify `/api/health`, `/api/config/status`, candle retrieval and quote status on the API host, then reload the Pages app.

If `GOLD_TERMINAL_API_BASE_URL` is unset, the frontend uses same-origin relative API paths. That is useful for local/reverse-proxy deployment but **will not connect FastAPI through GitHub Pages**. Never put bridge tokens or provider secrets in a GitHub Actions variable or frontend build variable.


## Free external PostgreSQL storage (Neon)

The API supports an external PostgreSQL database without changing the Render Free web service:

1. Create a project on the Neon Free plan at https://neon.com and choose the nearest available region to the Render service.
2. In Neon, open **Connect** and copy the PostgreSQL connection string. Keep the password private.
3. In the Render dashboard for the `gold-terminal-api` service, open **Environment** and add `DATABASE_URL` with that connection string. Do not put this value in GitHub, the frontend, or chat.
4. Save the environment change and wait for the Render deploy/restart to finish.
5. Open `/api/config/status`. The `historical_store` field should report `postgresql`. If it reports `sqlite`, the environment variable was not applied or the service has not restarted.
6. Import historical candles again or reconnect the MT5 bridge. Existing SQLite rows on the Render Free filesystem are not automatically migrated to Neon; export/import them before relying on the new database if those rows must be retained.

The app uses PostgreSQL when `DATABASE_URL` is present and falls back to SQLite when it is absent. The free database may scale to zero or suspend when its provider quota is reached; this is a free-tier hobby setup, not a guaranteed always-on production database. Monitor the provider's current quotas and keep an independent export of important historical candles.
