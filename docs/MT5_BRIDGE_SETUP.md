# MT5 XAUUSD Candle Bridge Setup

The repository includes `mt5/GoldLiquidityBridge.mq5`. It sends the last 300 **closed** candles for 4H, 1H, 15M and 5M to the app every 60 seconds. The 1H timeframe remains the only primary trade-direction and trade-plan source.

## 1. Configure the API server

Set a long random secret in the server environment. Do not commit it or put it in the browser:

```bash
export MARKET_INGEST_TOKEN='replace-with-a-long-random-secret'
export CANDLE_DB_PATH='data/market_candles.sqlite3'
export MAX_SPREAD_POINTS='0' # set a measured numeric broker limit before enabling BUY/SELL
uvicorn main:app --app-dir server --host 127.0.0.1 --port 8765
```

For Windows PowerShell:

```powershell
$env:MARKET_INGEST_TOKEN = "replace-with-a-long-random-secret"
$env:CANDLE_DB_PATH = "data/market_candles.sqlite3"
$env:MAX_SPREAD_POINTS = "0" # set a measured numeric broker limit before enabling BUY/SELL
uvicorn main:app --app-dir server --host 127.0.0.1 --port 8765
```

Use HTTPS and a protected server for remote connections. Do not expose an unauthenticated API port to the public internet.

## 2. Install the EA in MetaTrader 5

1. Open MT5 desktop and press **F4** to open MetaEditor.
2. Copy `mt5/GoldLiquidityBridge.mq5` into `MQL5/Experts/`.
3. Compile it in MetaEditor.
4. In MT5, open **Tools → Options → Expert Advisors**.
5. Enable **Allow WebRequest for listed URL** and add the exact API host, e.g. `http://127.0.0.1:8765` for same-PC local testing.
6. Attach **GoldLiquidityBridge** to an XAUUSD chart. In Inputs, set the API base URL and the same secret as `MARKET_INGEST_TOKEN`.
7. Confirm the MT5 Experts/Journal tab shows HTTP 200 responses.

If the broker uses a suffix (for example `XAUUSDm`), change `InpSymbol` to that exact Market Watch symbol. The bridge maps the feed into the app's canonical XAUUSD symbol.

## 3. Verify

- `GET /api/config/status` should show `live_data: true` after recent authenticated EA updates.
- `GET /api/market/candles?timeframe=1h&limit=300` should return imported closed candles.
- `GET /api/market/quote` should show a fresh quote and whether it passes the configured spread limit.
- The web dashboard should show candles after refresh.

The EA also sends current broker Bid/Ask snapshots to `/api/market/quote/bridge`. Set `MAX_SPREAD_POINTS` to a limit appropriate for your broker's XAUUSD digits and normal spread; until a positive limit is configured and a fresh quote is received, the spread gate stays closed and the report returns WAIT.

The bridge resends historical closed candles, so the SQLite store is upserted by symbol/timeframe/timestamp. The server requires recent MT5 candle uploads and checks the timestamp of the actual last broker tick (not just the timer's last HTTP request) before allowing the spread gate to pass. Both checks use a 180-second freshness window.

## Important limits

- MT5 tick volume is broker-specific tick activity, not centralized traded volume.
- Different brokers may quote different XAUUSD prices and candle boundaries.
- The bridge sends closed candles only; it does not send order-book depth, true bid/ask delta, exchange MBO, open interest, or institutional identity.
- The bridge does not place, modify, or close trades.
- A green connection status does not validate strategy profitability or Pine Script parity.
- Keep the token secret. Rotate it if it is exposed.
