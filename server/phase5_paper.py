"""Phase 5 persistent closed-candle forward paper-trading primitives.

This module never connects to a broker trading endpoint and never sends orders.
The API invokes it after authenticated MT5 quote ingestion.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_PAPER_STATE: dict[str, Any] = {
    "enabled": False,
    "max_spread_points": None,
    "slippage_points": 0.0,
    "commission_points_per_side": 0.0,
    "pending_signal": None,
    "last_processed_candle_time": None,
    "started_at": None,
    "stopped_at": None,
    "last_cycle": None,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number.")
    return number


def normalize_paper_config(candidate: dict[str, Any], current: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ValueError("Paper-forward configuration must be an object.")
    base = {**DEFAULT_PAPER_STATE, **(current or {})}
    allowed = ("enabled", "max_spread_points", "slippage_points", "commission_points_per_side")
    for key in allowed:
        if key in candidate:
            base[key] = candidate[key]
    if not isinstance(base.get("enabled"), bool):
        raise ValueError("enabled must be true or false.")
    cap = base.get("max_spread_points")
    if cap in (None, ""):
        base["max_spread_points"] = None
    else:
        cap = _finite(cap, "max_spread_points")
        if cap <= 0:
            raise ValueError("max_spread_points must be greater than zero.")
        base["max_spread_points"] = cap
    for key in ("slippage_points", "commission_points_per_side"):
        number = _finite(base.get(key, 0), key)
        if number < 0 or number > 100000:
            raise ValueError(f"{key} must be between 0 and 100000.")
        base[key] = number
    return base


class PaperForwardStore:
    """Durable SQLite/PostgreSQL storage for paper-forward state, events and trades."""

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
        if self.backend == "postgresql":
            state_id_type = "SMALLINT"
            time_type = "BIGINT"
            number_type = "DOUBLE PRECISION"
        else:
            state_id_type = "INTEGER"
            time_type = "INTEGER"
            number_type = "REAL"
        with self._connect() as db:
            db.execute(f"""CREATE TABLE IF NOT EXISTS paper_forward_state (
                state_id {state_id_type} PRIMARY KEY, state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL)""")
            db.execute(f"""CREATE TABLE IF NOT EXISTS paper_forward_events (
                event_id TEXT PRIMARY KEY, candle_time {time_type} NOT NULL UNIQUE,
                decision TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL,
                payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_paper_events_time ON paper_forward_events(candle_time)")
            db.execute(f"""CREATE TABLE IF NOT EXISTS paper_forward_trades (
                trade_id TEXT PRIMARY KEY, entry_time {time_type} NOT NULL, status TEXT NOT NULL,
                side TEXT NOT NULL, net_pnl_price {number_type}, pnl_r {number_type},
                payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_paper_trades_entry ON paper_forward_trades(entry_time)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_paper_trades_status ON paper_forward_trades(status)")
            initial = json.dumps(DEFAULT_PAPER_STATE, separators=(",", ":"), allow_nan=False)
            db.execute(self._sql("""INSERT INTO paper_forward_state(state_id,state_json,updated_at)
                VALUES(1,?,?) ON CONFLICT(state_id) DO NOTHING"""), (initial, _now()))

    def get_state(self) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(self._sql("SELECT state_json FROM paper_forward_state WHERE state_id=1")).fetchone()
        if not row:
            return dict(DEFAULT_PAPER_STATE)
        try:
            data = json.loads(row["state_json"])
        except (TypeError, ValueError):
            data = {}
        return {**DEFAULT_PAPER_STATE, **(data if isinstance(data, dict) else {})}

    def save_state(self, state: dict[str, Any]) -> dict[str, Any]:
        clean = {**DEFAULT_PAPER_STATE, **state}
        encoded = json.dumps(clean, separators=(",", ":"), allow_nan=False)
        with self._connect() as db:
            db.execute(self._sql("""INSERT INTO paper_forward_state(state_id,state_json,updated_at)
                VALUES(1,?,?) ON CONFLICT(state_id) DO UPDATE SET
                state_json=excluded.state_json,updated_at=excluded.updated_at"""), (encoded, _now()))
        return clean

    def claim_event(self, candle_time: int, payload: dict[str, Any] | None = None) -> bool:
        now = _now()
        event_id = f"XAUUSD:1H:{int(candle_time)}"
        encoded = json.dumps(payload or {}, separators=(",", ":"), allow_nan=False)
        with self._connect() as db:
            cursor = db.execute(self._sql("""INSERT INTO paper_forward_events(
                event_id,candle_time,decision,status,reason,payload,created_at,updated_at)
                VALUES(?,?, 'PROCESSING','PROCESSING','',?,?,?)
                ON CONFLICT(candle_time) DO NOTHING"""),
                (event_id, int(candle_time), encoded, now, now))
            return cursor.rowcount == 1

    def finish_event(
        self, candle_time: int, decision: str, status: str, reason: str,
        payload: dict[str, Any],
    ) -> None:
        now = _now()
        encoded = json.dumps(payload, separators=(",", ":"), allow_nan=False)
        with self._connect() as db:
            db.execute(self._sql("""UPDATE paper_forward_events SET decision=?,status=?,reason=?,
                payload=?,updated_at=? WHERE candle_time=?"""),
                (str(decision), str(status), str(reason)[:1000], encoded, now, int(candle_time)))

    def fail_event(self, candle_time: int, error: str) -> None:
        self.finish_event(candle_time, "WAIT", "ERROR", str(error), {"error": str(error), "paper_only": True})

    def list_events(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as db:
            rows = db.execute(self._sql("""SELECT * FROM paper_forward_events
                ORDER BY candle_time DESC LIMIT ?"""), (limit,)).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item.get("payload") or "{}")
            except (TypeError, ValueError):
                item["payload"] = {}
            out.append(item)
        return out

    def list_trades(self, limit: int = 200) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 1000))
        with self._connect() as db:
            rows = db.execute(self._sql("""SELECT * FROM paper_forward_trades
                ORDER BY entry_time DESC LIMIT ?"""), (limit,)).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            try:
                payload = json.loads(item.pop("payload") or "{}")
            except (TypeError, ValueError):
                payload = {}
            out.append({**payload, **item})
        return out

    def save_trade(self, trade: dict[str, Any]) -> dict[str, Any]:
        trade_id = str(trade.get("id") or uuid4())
        now = _now()
        payload = {**trade, "id": trade_id}
        encoded = json.dumps(payload, separators=(",", ":"), allow_nan=False)
        with self._connect() as db:
            db.execute(self._sql("""INSERT INTO paper_forward_trades(
                trade_id,entry_time,status,side,net_pnl_price,pnl_r,payload,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(trade_id) DO UPDATE SET status=excluded.status,
                net_pnl_price=excluded.net_pnl_price,pnl_r=excluded.pnl_r,
                payload=excluded.payload,updated_at=excluded.updated_at"""),
                (trade_id, int(payload["entry_time"]), str(payload["status"]), str(payload["side"]),
                 payload.get("net_pnl_price"), payload.get("pnl_r"), encoded,
                 str(payload.get("created_at") or now), now))
        return payload

    def summary(self) -> dict[str, Any]:
        trades = self.list_trades(1000)
        events = self.list_events(500)
        closed = [x for x in trades if x.get("status") == "CLOSED"]
        open_count = sum(x.get("status") == "OPEN" for x in trades)
        wins = [x for x in closed if _safe_num(x.get("pnl_r")) > 0]
        losses = [x for x in closed if _safe_num(x.get("pnl_r")) < 0]
        values = [_safe_num(x.get("pnl_r")) for x in sorted(closed, key=lambda t: int(t.get("entry_time") or 0))]
        net = sum(_safe_num(x.get("net_pnl_price")) for x in closed)
        gains = sum(_safe_num(x.get("pnl_r")) for x in wins)
        loss_abs = abs(sum(_safe_num(x.get("pnl_r")) for x in losses))
        equity = peak = max_drawdown = 0.0
        for value in values:
            equity += value
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
        return {
            "processed_events": len(events),
            "trades_total": len(trades),
            "trades_closed": len(closed),
            "trades_open": open_count,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(100 * len(wins) / len(closed), 2) if closed else None,
            "net_pnl_price": round(net, 5),
            "average_R": round(sum(values) / len(values), 4) if values else None,
            "profit_factor_R": round(gains / loss_abs, 4) if loss_abs else (None if not gains else "INF"),
            "max_drawdown_R": round(max_drawdown, 4),
            "pending_signal": self.get_state().get("pending_signal"),
        }


def _safe_num(value: Any) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else 0.0
    except (TypeError, ValueError):
        return 0.0


def journal_view_from_paper_trades(trades: list[dict[str, Any]], contract_size: float | None) -> list[dict[str, Any]]:
    """Adapt Phase 5 paper positions to the existing risk gate's read-only journal shape."""
    output = []
    for trade in trades:
        entry_time = int(trade.get("entry_time") or trade.get("signal_time") or 0)
        closed_time = trade.get("exit_time")
        pnl_money = None
        lots = trade.get("lots")
        if contract_size and lots and trade.get("net_pnl_price") is not None:
            pnl_money = _safe_num(trade["net_pnl_price"]) * float(lots) * float(contract_size)
        output.append({
            "status": trade.get("status"),
            "opened_at": datetime.fromtimestamp(entry_time, timezone.utc).isoformat() if entry_time else None,
            "created_at": datetime.fromtimestamp(entry_time, timezone.utc).isoformat() if entry_time else None,
            "closed_at": datetime.fromtimestamp(int(closed_time), timezone.utc).isoformat() if closed_time else None,
            "pnl_money": pnl_money,
        })
    return output


def advance_open_trade(
    trade: dict[str, Any],
    candle: dict[str, Any],
    *,
    spread_points: float,
    point_size: float,
    slippage_points: float,
    commission_points_per_side: float,
) -> dict[str, Any] | None:
    """Close at stop or TP1; ambiguous bars are resolved stop-first."""
    side = str(trade.get("side", "")).upper()
    sign = 1.0 if side == "BUY" else -1.0 if side == "SELL" else 0.0
    if not sign:
        raise ValueError("Paper trade side must be BUY or SELL.")
    high, low = _safe_num(candle.get("high")), _safe_num(candle.get("low"))
    opened = _safe_num(candle.get("open"))
    stop, target = _safe_num(trade.get("stop_loss")), _safe_num(trade.get("tp1"))
    stop_hit = low <= stop if side == "BUY" else high >= stop
    target_hit = high >= target if side == "BUY" else low <= target
    if not stop_hit and not target_hit:
        return None
    if stop_hit:
        raw_exit = min(stop, opened) if side == "BUY" else max(stop, opened)
        reason = "STOP_FIRST" if target_hit else "STOP"
    else:
        raw_exit = target
        reason = "TP1"
    exit_cost = (spread_points / 2.0 + slippage_points) * point_size
    commission = commission_points_per_side * point_size * 2.0
    exit_fill = raw_exit - sign * exit_cost
    entry_fill = _safe_num(trade.get("entry_price"))
    entry_reference = _safe_num(trade.get("entry_reference_price", entry_fill))
    gross = sign * (raw_exit - entry_reference)
    net = sign * (exit_fill - entry_fill) - commission
    risk_unit = max(_safe_num(trade.get("risk_unit")), 1e-12)
    return {
        **trade,
        "status": "CLOSED",
        "exit_time": int(candle["time"]) + 3600,
        "exit_reference_price": raw_exit,
        "exit_price": exit_fill,
        "exit_reason": reason,
        "gross_pnl_price": round(gross, 6),
        "net_pnl_price": round(net, 6),
        "pnl_r": round(net / risk_unit, 5),
        "exit_costs": {
            "spread_points": spread_points,
            "slippage_points": slippage_points,
            "commission_points_per_side": commission_points_per_side,
        },
        "updated_at": _now(),
    }


def open_from_pending(
    pending: dict[str, Any],
    candle: dict[str, Any],
    *,
    spread_points: float,
    point_size: float,
    slippage_points: float,
    commission_points_per_side: float,
) -> tuple[dict[str, Any] | None, str]:
    """Simulate next-1H-open entry only when it opens inside the prior 1H zone."""
    side = str(pending.get("side", "")).upper()
    if side not in {"BUY", "SELL"}:
        return None, "INVALID_PENDING_DIRECTION"
    plan = pending.get("trade_plan") or {}
    entry_zone = plan.get("entry")
    targets = plan.get("targets")
    if not isinstance(entry_zone, list) or len(entry_zone) != 2 or not isinstance(targets, list) or len(targets) != 3:
        return None, "INVALID_PENDING_PLAN"
    low, high = sorted((_safe_num(entry_zone[0]), _safe_num(entry_zone[1])))
    reference = _safe_num(candle.get("open"))
    if not low <= reference <= high:
        return None, "ENTRY_ZONE_MISSED_NO_CHASE"
    sign = 1.0 if side == "BUY" else -1.0
    entry_cost = (spread_points / 2.0 + slippage_points) * point_size
    entry_fill = reference + sign * entry_cost
    stop = _safe_num(plan.get("stop_loss"))
    target_values = [_safe_num(x) for x in targets]
    if side == "BUY":
        valid = stop < entry_fill < target_values[0] < target_values[1] < target_values[2]
    else:
        valid = stop > entry_fill > target_values[0] > target_values[1] > target_values[2]
    if not valid:
        return None, "INVALID_LEVEL_ORDER_AFTER_COSTS"
    risk_unit = abs(entry_fill - stop)
    lots = (pending.get("position_size") or {}).get("estimated_lots")
    trade = {
        "id": f"paper-XAUUSD-1H-{int(candle['time'])}-{side}",
        "symbol": "XAUUSD",
        "side": side,
        "signal_time": int(pending.get("signal_time") or 0),
        "entry_time": int(candle["time"]),
        "entry_reference_price": reference,
        "entry_price": entry_fill,
        "stop_loss": stop,
        "tp1": target_values[0],
        "tp2": target_values[1],
        "tp3": target_values[2],
        "risk_unit": risk_unit,
        "status": "OPEN",
        "exit_time": None,
        "exit_price": None,
        "exit_reason": None,
        "gross_pnl_price": None,
        "net_pnl_price": None,
        "pnl_r": None,
        "lots": lots,
        "entry_costs": {
            "spread_points": spread_points,
            "slippage_points": slippage_points,
            "commission_points_per_side": commission_points_per_side,
        },
        "execution": "NEXT_1H_OPEN_SIMULATION",
        "paper_only": True,
        "created_at": _now(),
        "updated_at": _now(),
    }
    return trade, "ENTRY_OPENED"


def performance_summary(trades: list[dict[str, Any]], event_count: int, pending_signal: dict[str, Any] | None) -> dict[str, Any]:
    closed = [x for x in trades if x.get("status") == "CLOSED"]
    ordered = sorted(closed, key=lambda x: int(x.get("entry_time") or 0))
    rs = [_safe_num(x.get("pnl_r")) for x in ordered]
    wins = sum(x > 0 for x in rs)
    losses = sum(x < 0 for x in rs)
    gains = sum(x for x in rs if x > 0)
    loss_abs = abs(sum(x for x in rs if x < 0))
    equity = peak = max_dd = 0.0
    for value in rs:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        "processed_events": event_count,
        "trades_total": len(trades),
        "trades_closed": len(closed),
        "trades_open": sum(x.get("status") == "OPEN" for x in trades),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": round(100 * wins / len(closed), 2) if closed else None,
        "net_pnl_price": round(sum(_safe_num(x.get("net_pnl_price")) for x in closed), 5),
        "average_R": round(sum(rs) / len(rs), 4) if rs else None,
        "profit_factor_R": round(gains / loss_abs, 4) if loss_abs else (None if not gains else "INF"),
        "max_drawdown_R": round(max_dd, 4),
        "pending_signal": pending_signal,
    }
