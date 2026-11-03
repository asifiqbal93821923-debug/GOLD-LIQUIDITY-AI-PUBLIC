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
