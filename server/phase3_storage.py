"""Durable Phase 3 storage for risk settings, signal alerts and a manual trade journal."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

class Phase3Store:
    def __init__(self, path: str):
        self.backend = "postgresql" if path.startswith(("postgres://", "postgresql://")) else "sqlite"
        self.path = path if self.backend == "postgresql" else Path(path)
        if self.backend == "sqlite":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        if self.backend == "postgresql":
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise RuntimeError("DATABASE_URL requires psycopg[binary].") from exc
            return psycopg.connect(self.path, row_factory=dict_row, connect_timeout=10)
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        return db

    def _sql(self, query: str) -> str:
        return query.replace("?", "%s") if self.backend == "postgresql" else query

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS signal_events (
                id TEXT PRIMARY KEY, signal_key TEXT NOT NULL UNIQUE, symbol TEXT NOT NULL,
                direction TEXT NOT NULL, candle_time BIGINT NOT NULL, price DOUBLE PRECISION,
                entry_low DOUBLE PRECISION, entry_high DOUBLE PRECISION, stop_loss DOUBLE PRECISION,
                target1 DOUBLE PRECISION, target2 DOUBLE PRECISION, target3 DOUBLE PRECISION,
                reason_codes TEXT NOT NULL, created_at TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_signal_events_created ON signal_events(created_at)")
            db.execute("""CREATE TABLE IF NOT EXISTS trade_journal (
                id TEXT PRIMARY KEY, symbol TEXT NOT NULL, direction TEXT NOT NULL, status TEXT NOT NULL,
                entry_price DOUBLE PRECISION NOT NULL, stop_loss DOUBLE PRECISION NOT NULL,
                target_price DOUBLE PRECISION NOT NULL, exit_price DOUBLE PRECISION, lots DOUBLE PRECISION NOT NULL,
                pnl_money DOUBLE PRECISION, notes TEXT NOT NULL, opened_at TEXT NOT NULL, closed_at TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_trade_journal_created ON trade_journal(created_at)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_trade_journal_status ON trade_journal(status)")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._connect() as db:
            row = db.execute(self._sql("SELECT setting_value FROM app_settings WHERE setting_key=?"), (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["setting_value"])
        except (TypeError, ValueError):
            return default

    def set_setting(self, key: str, value: Any) -> None:
        encoded = json.dumps(value, separators=(",", ":"), allow_nan=False)
        with self._connect() as db:
            db.execute(self._sql("""INSERT INTO app_settings(setting_key,setting_value,updated_at)
                VALUES(?,?,?) ON CONFLICT(setting_key) DO UPDATE SET
                setting_value=excluded.setting_value,updated_at=excluded.updated_at"""),
                (key, encoded, self._now()))

    def get_risk_settings(self, defaults: dict[str, Any]) -> dict[str, Any]:
        saved = self.get_setting("risk_settings:XAUUSD", {})
        return {**defaults, **(saved if isinstance(saved, dict) else {})}

    def set_risk_settings(self, settings: dict[str, Any]) -> None:
        self.set_setting("risk_settings:XAUUSD", settings)

    def create_signal_event(self, event: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        event_id, created_at = str(uuid4()), self._now()
        values = (event_id, event["signal_key"], event.get("symbol", "XAUUSD"), event["direction"],
            int(event["candle_time"]), event.get("price"), event.get("entry_low"), event.get("entry_high"),
            event.get("stop_loss"), event.get("target1"), event.get("target2"), event.get("target3"),
            json.dumps(event.get("reason_codes", []), separators=(",", ":")), created_at)
        with self._connect() as db:
            db.execute(self._sql("""INSERT INTO signal_events(
                id,signal_key,symbol,direction,candle_time,price,entry_low,entry_high,stop_loss,
                target1,target2,target3,reason_codes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(signal_key) DO NOTHING"""), values)
            row = db.execute(self._sql("SELECT * FROM signal_events WHERE signal_key=?"),
                              (event["signal_key"],)).fetchone()
        result = dict(row)
        result["reason_codes"] = json.loads(result.get("reason_codes") or "[]")
        return result, result["id"] == event_id

    def list_signal_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(self._sql("SELECT * FROM signal_events ORDER BY created_at DESC LIMIT ?"),
                              (max(1, min(int(limit), 200)),)).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                item["reason_codes"] = json.loads(item.get("reason_codes") or "[]")
            except (TypeError, ValueError):
                item["reason_codes"] = []
            out.append(item)
        return out

    def create_journal_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        entry_id, now = str(uuid4()), self._now()
        values = (entry_id, "XAUUSD", entry["direction"], "OPEN", entry["entry_price"], entry["stop_loss"],
            entry["target_price"], None, entry["lots"], None, entry.get("notes", "")[:500], now, None, now, now)
        with self._connect() as db:
            db.execute(self._sql("""INSERT INTO trade_journal(
                id,symbol,direction,status,entry_price,stop_loss,target_price,exit_price,lots,pnl_money,
                notes,opened_at,closed_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""), values)
            row = db.execute(self._sql("SELECT * FROM trade_journal WHERE id=?"), (entry_id,)).fetchone()
        return dict(row)

    def close_journal_entry(self, entry_id: str, exit_price: float, pnl_money: float) -> dict[str, Any] | None:
        now = self._now()
        with self._connect() as db:
            cursor = db.execute(self._sql("""UPDATE trade_journal SET status='CLOSED',exit_price=?,
                pnl_money=?,closed_at=?,updated_at=? WHERE id=? AND status='OPEN'"""),
                (exit_price, pnl_money, now, now, entry_id))
            if cursor.rowcount == 0:
                return None
            row = db.execute(self._sql("SELECT * FROM trade_journal WHERE id=?"), (entry_id,)).fetchone()
        return dict(row) if row else None

    def list_journal_entries(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(self._sql("SELECT * FROM trade_journal ORDER BY created_at DESC LIMIT ?"),
                              (max(1, min(int(limit), 500)),)).fetchall()
        return [dict(row) for row in rows]
