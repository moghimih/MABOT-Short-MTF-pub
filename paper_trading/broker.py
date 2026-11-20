"""Persistent local paper broker. This module never sends exchange orders."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Fill:
    side: str
    symbol: str
    quantity: float
    price: float
    fee: float
    cash_after: float


class PaperBroker:
    """Long-only spot simulator backed by SQLite.

    Market buys pay adverse slippage; sells receive adverse slippage.
    Fees are charged on notional. Each event_id is idempotent.
    """

    def __init__(
        self,
        db_path: str | Path,
        initial_cash: float = 100.0,
        fee_rate: float = 0.002,
        slippage_rate: float = 0.0005,
        max_open_positions: int = 2,
    ):
        if initial_cash <= 0 or fee_rate < 0 or slippage_rate < 0:
            raise ValueError("Invalid broker configuration")
        if max_open_positions < 1:
            raise ValueError("max_open_positions must be >= 1")
        self.db_path = str(db_path)
        self.fee_rate = float(fee_rate)
        self.slippage_rate = float(slippage_rate)
        self.max_open_positions = int(max_open_positions)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY CHECK(id=1), cash REAL NOT NULL)""")
            con.execute("""INSERT OR IGNORE INTO account(id,cash) VALUES(1,?)""",
                        (float(initial_cash),))
            con.execute("""CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY, quantity REAL NOT NULL,
                avg_entry REAL NOT NULL, stop_price REAL NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY, side TEXT NOT NULL, symbol TEXT NOT NULL,
                quantity REAL NOT NULL, price REAL NOT NULL, fee REAL NOT NULL,
                cash_after REAL NOT NULL)""")

    def _connect(self):
        con = sqlite3.connect(self.db_path, timeout=30)
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @property
    def cash(self) -> float:
        with self._connect() as con:
            return float(con.execute("SELECT cash FROM account WHERE id=1").fetchone()[0])

    def positions(self) -> dict:
        with self._connect() as con:
            rows = con.execute(
                "SELECT symbol,quantity,avg_entry,stop_price FROM positions"
            ).fetchall()
        return {s: {"quantity": q, "avg_entry": p, "stop_price": st}
                for s, q, p, st in rows}

    def trades(self) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT event_id,side,symbol,quantity,price,fee,cash_after "
                "FROM events ORDER BY rowid"
            ).fetchall()
        keys = ("event_id","side","symbol","quantity","price","fee","cash_after")
        return [dict(zip(keys, row)) for row in rows]

    def update_stop(self, symbol: str, stop_price: float) -> None:
        """Move the protective stop of an open position (trailing stops only move up)."""
        if not isinstance(stop_price, (int, float)) or not 0 < stop_price < float("inf"):
            raise ValueError("stop_price must be a positive finite number")
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT stop_price FROM positions WHERE symbol=?", (symbol,)).fetchone()
            if not row:
                raise ValueError(f"No open position for {symbol}")
            if stop_price < float(row[0]):
                raise ValueError("A stop may only be moved up")
            con.execute("UPDATE positions SET stop_price=? WHERE symbol=?", (float(stop_price), symbol))

    def _prior_event(self, con, event_id: str) -> Optional[Fill]:
        row = con.execute(
            "SELECT side,symbol,quantity,price,fee,cash_after FROM events WHERE event_id=?",
            (event_id,),
        ).fetchone()
        return Fill(*row) if row else None

    def buy(self, event_id: str, symbol: str, reference_price: float,
            quantity: float, stop_price: float) -> Optional[Fill]:
        self._validate_order(event_id, symbol, reference_price, quantity)
        if stop_price <= 0 or stop_price >= reference_price:
            raise ValueError("stop_price must be positive and below reference_price")
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            previous = self._prior_event(con, event_id)
            if previous:
                return previous
            existing = con.execute(
                "SELECT quantity FROM positions WHERE symbol=?", (symbol,)
            ).fetchone()
            if existing:
                raise ValueError(f"Position already open for {symbol}")
            count = con.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
            if count >= self.max_open_positions:
                raise ValueError("Maximum open positions reached")
            fill_price = reference_price * (1 + self.slippage_rate)
            notional = fill_price * quantity
            fee = notional * self.fee_rate
            cash = float(con.execute("SELECT cash FROM account WHERE id=1").fetchone()[0])
            total = notional + fee
            if total > cash + 1e-12:
                raise ValueError("Insufficient virtual cash")
            cash -= total
            con.execute("UPDATE account SET cash=? WHERE id=1", (cash,))
            con.execute("INSERT INTO positions VALUES(?,?,?,?)",
                        (symbol, quantity, fill_price, stop_price))
            con.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?)",
                        (event_id,"BUY",symbol,quantity,fill_price,fee,cash))
            return Fill("BUY",symbol,quantity,fill_price,fee,cash)

    def sell(self, event_id: str, symbol: str,
             reference_price: float) -> Optional[Fill]:
        self._validate_order(event_id, symbol, reference_price, 1.0)
        with self._connect() as con:
            con.execute("BEGIN IMMEDIATE")
            previous = self._prior_event(con, event_id)
            if previous:
                return previous
            row = con.execute(
                "SELECT quantity FROM positions WHERE symbol=?", (symbol,)
            ).fetchone()
            if not row:
                raise ValueError(f"No open position for {symbol}")
            quantity = float(row[0])
            fill_price = reference_price * (1 - self.slippage_rate)
            notional = fill_price * quantity
            fee = notional * self.fee_rate
            cash = float(con.execute("SELECT cash FROM account WHERE id=1").fetchone()[0])
            cash += notional - fee
            con.execute("UPDATE account SET cash=? WHERE id=1", (cash,))
            con.execute("DELETE FROM positions WHERE symbol=?", (symbol,))
            con.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?)",
                        (event_id,"SELL",symbol,quantity,fill_price,fee,cash))
            return Fill("SELL",symbol,quantity,fill_price,fee,cash)

    @staticmethod
    def _validate_order(event_id, symbol, price, quantity):
        if not event_id or not symbol:
            raise ValueError("event_id and symbol are required")
        if not all(map(lambda x: isinstance(x, (int,float)) and x > 0 and x < float("inf"),
                       (price, quantity))):
            raise ValueError("price and quantity must be positive finite numbers")
