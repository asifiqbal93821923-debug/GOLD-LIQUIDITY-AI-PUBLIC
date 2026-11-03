"""SQLite/PostgreSQL candle store. PostgreSQL can use a free external database; SQLite remains the local fallback."""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any

def to_epoch_seconds(value: Any) -> int:
    if isinstance(value,bool): raise ValueError("Candle time must be an epoch or ISO timestamp")
    if isinstance(value,(int,float)):
        n=float(value)
        if n>100_000_000_000: n/=1000.0
        if n<0: raise ValueError("Candle timestamp cannot be negative")
        return int(n)
    if isinstance(value,str):
        raw=value.strip()
        if not raw: raise ValueError("Candle time is empty")
        try:
            n=float(raw)
            return to_epoch_seconds(n)
        except ValueError:
            pass
        try:
            dt=datetime.fromisoformat(raw.replace("Z","+00:00"))
            if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError as exc:
            raise ValueError(f"Invalid candle timestamp: {value}") from exc
    raise ValueError("Unsupported candle timestamp type")

def validate_candles(rows: list[dict[str,Any]]) -> list[dict[str,Any]]:
    if not rows: raise ValueError("At least one candle is required")
    out=[]; seen=set()
    for i,row in enumerate(rows):
        try:
            ts=to_epoch_seconds(row.get("time"))
            o=float(row["open"]); h=float(row["high"]); l=float(row["low"]); c=float(row["close"])
            v=row.get("volume")
            v=None if v is None else float(v)
        except (KeyError,TypeError,ValueError) as exc:
            raise ValueError(f"Invalid candle at row {i}: {exc}") from exc
        vals=(o,h,l,c)
        if any(not __import__("math").isfinite(x) for x in vals) or (v is not None and not __import__("math").isfinite(v)):
            raise ValueError(f"Non-finite OHLCV value at row {i}")
        if h<max(o,c,l) or l>min(o,c,h):
            raise ValueError(f"Impossible OHLC range at row {i}")
        if v is not None and v<0: raise ValueError(f"Negative volume at row {i}")
        if ts in seen: raise ValueError(f"Duplicate candle timestamp: {ts}")
        seen.add(ts)
        out.append({"time":ts,"symbol":str(row.get("symbol","XAUUSD")).upper(),
                    "open":o,"high":h,"low":l,"close":c,"volume":v})
    out.sort(key=lambda x:x["time"])
    return out

class CandleStore:
    def __init__(self,path: str):
        self.backend="postgresql" if path.startswith(("postgres://","postgresql://")) else "sqlite"
        self.path=path if self.backend=="postgresql" else Path(path)
        if self.backend=="sqlite":
            self.path.parent.mkdir(parents=True,exist_ok=True)
            with self._connect() as db:
                db.execute("""CREATE TABLE IF NOT EXISTS candles(
                  symbol TEXT NOT NULL,timeframe TEXT NOT NULL,time INTEGER NOT NULL,
                  open REAL NOT NULL,high REAL NOT NULL,low REAL NOT NULL,close REAL NOT NULL,
                  volume REAL,source TEXT NOT NULL,updated_at TEXT NOT NULL,
                  PRIMARY KEY(symbol,timeframe,time))""")
                db.execute("CREATE INDEX IF NOT EXISTS idx_candles_lookup ON candles(symbol,timeframe,time)")
                db.execute("""CREATE TABLE IF NOT EXISTS quotes(
                  symbol TEXT PRIMARY KEY,bid REAL NOT NULL,ask REAL NOT NULL,point REAL NOT NULL,
                  spread_points REAL NOT NULL,quote_time INTEGER NOT NULL,source TEXT NOT NULL,updated_at TEXT NOT NULL)""")
        else:
            with self._connect() as db:
                db.execute("""CREATE TABLE IF NOT EXISTS candles(
                  symbol TEXT NOT NULL,timeframe TEXT NOT NULL,time BIGINT NOT NULL,
                  open DOUBLE PRECISION NOT NULL,high DOUBLE PRECISION NOT NULL,
                  low DOUBLE PRECISION NOT NULL,close DOUBLE PRECISION NOT NULL,
                  volume DOUBLE PRECISION,source TEXT NOT NULL,updated_at TEXT NOT NULL,
                  PRIMARY KEY(symbol,timeframe,time))""")
                db.execute("CREATE INDEX IF NOT EXISTS idx_candles_lookup ON candles(symbol,timeframe,time)")
                db.execute("""CREATE TABLE IF NOT EXISTS quotes(
                  symbol TEXT PRIMARY KEY,bid DOUBLE PRECISION NOT NULL,ask DOUBLE PRECISION NOT NULL,
                  point DOUBLE PRECISION NOT NULL,spread_points DOUBLE PRECISION NOT NULL,
                  quote_time BIGINT NOT NULL,source TEXT NOT NULL,updated_at TEXT NOT NULL)""")

    def _connect(self):
        if self.backend=="postgresql":
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise RuntimeError("DATABASE_URL requires psycopg[binary]. Install server requirements.") from exc
            return psycopg.connect(self.path, row_factory=dict_row, connect_timeout=10)
        db=sqlite3.connect(self.path,timeout=20)
        db.row_factory=sqlite3.Row
        return db

    def _sql(self,query: str) -> str:
        return query.replace("?","%s") if self.backend=="postgresql" else query

    def upsert(self,symbol: str,timeframe: str,rows: list[dict[str,Any]],source: str) -> int:
        now=datetime.now(timezone.utc).isoformat()
        values=[(symbol,timeframe,x["time"],x["open"],x["high"],x["low"],x["close"],x.get("volume"),source,now) for x in rows]
        with self._connect() as db:
            db.executemany(self._sql("""INSERT INTO candles(symbol,timeframe,time,open,high,low,close,volume,source,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(symbol,timeframe,time) DO UPDATE SET
              open=excluded.open,high=excluded.high,low=excluded.low,close=excluded.close,
              volume=excluded.volume,source=excluded.source,updated_at=excluded.updated_at"""),values)
        return len(values)

    def read(self,symbol: str,timeframe: str,limit: int=1000) -> list[dict[str,Any]]:
        with self._connect() as db:
            rows=db.execute(self._sql("""SELECT time,open,high,low,close,volume FROM candles
              WHERE symbol=? AND timeframe=? ORDER BY time DESC LIMIT ?"""),(symbol,timeframe,limit)).fetchall()
        return [dict(x) for x in reversed(rows)]

    def count(self,symbol: str,timeframe: str) -> int:
        with self._connect() as db:
            row=db.execute(self._sql("SELECT COUNT(*) AS n FROM candles WHERE symbol=? AND timeframe=?"),(symbol,timeframe)).fetchone()
        return int(row["n"])

    def latest_ingest(self,symbol: str="XAUUSD",timeframe: str | None=None) -> dict[str,Any] | None:
        with self._connect() as db:
            if timeframe:
                row=db.execute(self._sql("""SELECT source,updated_at FROM candles WHERE symbol=? AND timeframe=?
                  ORDER BY updated_at DESC LIMIT 1"""),(symbol,timeframe)).fetchone()
            else:
                row=db.execute(self._sql("""SELECT source,updated_at FROM candles WHERE symbol=?
                  ORDER BY updated_at DESC LIMIT 1"""),(symbol,)).fetchone()
        return dict(row) if row else None

    def upsert_quote(self,symbol: str,bid: float,ask: float,point: float,quote_time: int,source: str) -> None:
        now=datetime.now(timezone.utc).isoformat()
        spread=(ask-bid)/point
        with self._connect() as db:
            db.execute(self._sql("""INSERT INTO quotes(symbol,bid,ask,point,spread_points,quote_time,source,updated_at)
              VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET
              bid=excluded.bid,ask=excluded.ask,point=excluded.point,spread_points=excluded.spread_points,
              quote_time=excluded.quote_time,source=excluded.source,updated_at=excluded.updated_at"""),
              (symbol,bid,ask,point,spread,quote_time,source,now))

    def latest_quote(self,symbol: str="XAUUSD") -> dict[str,Any] | None:
        with self._connect() as db:
            row=db.execute(self._sql("SELECT * FROM quotes WHERE symbol=?"),(symbol,)).fetchone()
        return dict(row) if row else None
