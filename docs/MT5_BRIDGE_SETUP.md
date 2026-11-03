# MT5 XAUUSD Candle Bridge Setup

The repository includes `mt5/GoldLiquidityBridge.mq5`. It sends the last 300 **closed** candles for 4H, 1H, 15M and 5M to the app every 60 seconds. The 1H timeframe remains the only primary trade-direction and trade-plan source. The EA is a data bridge only: it never submits trades.

The API now checks both server receive time and the actual timestamp of the latest closed candle. Reposting old candles cannot keep the LIVE gate open. The latest candle must have closed and be no older than one timeframe plus a 180-second grace window.

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
3. Compile it in MetaEditor. Confirm **0 errors** in the Toolbox/Errors tab. A successful GitHub build does not compile MQL5 code.
4. In MT5, open **Tools → Options → Expert Advisors**.
5. Enable **Allow WebRequest for listed URL** and add the exact API host, e.g. `http://127.0.0.1:8765` for same-PC local testing.
6. Attach **GoldLiquidityBridge** to an XAUUSD chart. In Inputs, set the API base URL and the same secret as `MARKET_INGEST_TOKEN`. If your broker's symbol is suffixed (such as `XAUUSDm` or `GOLD.`), set `InpSymbol` to the exact Market Watch symbol. The EA maps it to the app's canonical XAUUSD label.
7. Confirm the MT5 Experts/Journal tab shows HTTP 200 responses.

If the broker uses a suffix (for example `XAUUSDm`), change `InpSymbol` to that exact Market Watch symbol. The bridge maps the feed into the app's canonical XAUUSD symbol.

## 3. Verify

- `GET /api/config/status` should show `live_data: true` only when 4H/1H/15M latest candles and the broker tick are all fresh. Inspect `timeframe_health` for each timeframe's last candle close age and receive age.
- `GET /api/market/candles?timeframe=1h&limit=300` should return imported closed candles.
- `GET /api/market/quote` should show a fresh quote and whether it passes the configured spread limit.
- The web dashboard should show candles after refresh.

The EA also sends current broker Bid/Ask snapshots to `/api/market/quote/bridge`. Set `MAX_SPREAD_POINTS` to a limit appropriate for your broker's XAUUSD digits and normal spread; until a positive limit is configured and a fresh quote is received, the spread gate stays closed and the report returns WAIT.

The bridge resends historical closed candles, so the SQLite store is upserted by symbol/timeframe/timestamp. The server requires recent MT5 candle uploads, verifies the latest bar is closed and no older than one full timeframe plus 180 seconds, and checks the timestamp of the actual last broker tick (not just the timer's last HTTP request). The HTTP receive and tick freshness windows are 180 seconds.

## Network and broker calibration

- If MT5 and the API run on the **same Windows PC**, `http://127.0.0.1:8765` is suitable for a local test.
- If MT5 runs on a PC and the API is hosted on a VPS, `127.0.0.1` is wrong: it points to the MT5 PC itself. Use the API's HTTPS domain in both `InpApiBaseUrl` and the MT5 WebRequest allow-list.
- Do not expose port 8765 directly to the public internet. Put the API behind HTTPS/reverse proxy and firewall it.
- Keep `MAX_SPREAD_POINTS=0` during initial connection testing. This deliberately keeps trade reports at WAIT. Observe the broker's actual spread in `/api/market/quote` across active sessions, verify the symbol's `SYMBOL_POINT` and digits, then choose a conservative limit in the same **points** unit. Do not copy a generic XAUUSD spread number from another broker.
- For a basic server check, open `/api/health`, then `/api/config/status`, `/api/market/candles?timeframe=1h&limit=5`, and `/api/market/quote`. A 200 response from `/api/health` alone does not mean MT5 is connected.
- If candle upload returns HTTP 422, check that MT5 history is synchronized and the most recent closed candle is actually available. HTTP 401 means the EA and server tokens do not match. WebRequest error 4014 commonly means the API host is not allow-listed in MT5.

## Important limits

- MT5 tick volume is broker-specific tick activity, not centralized traded volume.
- Different brokers may quote different XAUUSD prices and candle boundaries.
- The bridge sends closed candles only; it does not send order-book depth, true bid/ask delta, exchange MBO, open interest, or institutional identity.
- The bridge does not place, modify, or close trades.
- A green connection status does not validate strategy profitability or Pine Script parity.
- Keep the token secret. Rotate it if it is exposed.
