"""Safe multi-timeframe paper runner. Public data and simulated fills only."""
from __future__ import annotations

import argparse
import math
import sqlite3
import time
from pathlib import Path

import pandas as pd

from config.settings import (FEE_RATE, INITIAL_CAPITAL, MAX_OPEN_POSITIONS,
                             MAX_PORTFOLIO_RISK, MAX_RISK_PER_TRADE,
                             PAPER_TRADING_ENABLED, SLIPPAGE_RATE, SYMBOLS)
from paper_trading.broker import PaperBroker
from paper_trading.live_signals import prepare_breakout_frame
from paper_trading.market_data import NobitexPublicDataClient
from paper_trading.ops import configure_logging, retry_call
from risk.portfolio_risk import check_portfolio_risk
from risk.position_sizing import calculate_position_size
from risk.stop_loss import update_trailing_stop

# Same ATR stop multiple as RiskBacktestEngine's default, so paper == validated backtest logic.
ATR_STOP_MULTIPLIER = 2.5


class PaperSignalRunner:
    """Runs the validated BREAKOUT + risk-engine logic on closed candles, simulated fills only.

    Rules (mirroring backtesting/engine_with_risk.py):
      * ATR initial stop = entry - ATR*2.5 (ATR of the signal candle), ATR trailing stop moves up only;
      * position size from 1% equity risk (fees+slippage included) and a 2% portfolio-risk cap;
      * equity values every open position at ITS OWN last close;
      * every closed candle is processed exactly once and in time order, also after downtime
        (catch-up), so no stop or signal is skipped when the runner was not running.
    Fills use the signal candle's close plus adverse slippage (the live-like proxy of the next open).
    """

    def __init__(self, db_path: str | Path, client=None, broker=None,
                 retry_attempts: int = 3, logger=None, timeframe: str = "4h"):
        if not PAPER_TRADING_ENABLED:
            raise RuntimeError("Paper trading is disabled in config")
        from paper_trading.market_data import TIMEFRAMES
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe {timeframe!r}; choose one of {tuple(TIMEFRAMES)}")
        self.timeframe = timeframe
        self.db_path = str(db_path)
        self.retry_attempts = int(retry_attempts)
        if self.retry_attempts < 1:
            raise ValueError("retry_attempts must be >= 1")
        self.logger = logger
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.client = client or NobitexPublicDataClient()
        self.broker = broker or PaperBroker(
            self.db_path, INITIAL_CAPITAL, FEE_RATE, SLIPPAGE_RATE, MAX_OPEN_POSITIONS
        )
        with sqlite3.connect(self.db_path) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS processed_candles (
                symbol TEXT NOT NULL, timestamp INTEGER NOT NULL,
                action TEXT NOT NULL, processed_at INTEGER NOT NULL,
                PRIMARY KEY(symbol,timestamp))""")
            con.execute("""CREATE TABLE IF NOT EXISTS marks (
                symbol TEXT PRIMARY KEY, price REAL NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS symbol_status (
                symbol TEXT PRIMARY KEY, timestamp INTEGER NOT NULL, close REAL NOT NULL,
                ema200 REAL, entry_channel REAL, bars_in_segment INTEGER, buy INTEGER NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS equity_snapshots (
                timestamp INTEGER PRIMARY KEY, equity REAL NOT NULL,
                cash REAL NOT NULL, open_positions INTEGER NOT NULL)""")

    # ------------------------------------------------------------ bookkeeping
    def _last_processed_ts(self, symbol: str):
        with sqlite3.connect(self.db_path) as con:
            row = con.execute("SELECT MAX(timestamp) FROM processed_candles WHERE symbol=?",
                              (symbol,)).fetchone()
        return None if row is None or row[0] is None else int(row[0])

    def _already_processed(self, symbol: str, timestamp: int) -> bool:
        with sqlite3.connect(self.db_path) as con:
            return con.execute("SELECT 1 FROM processed_candles WHERE symbol=? AND timestamp=?",
                               (symbol, int(timestamp))).fetchone() is not None

    def _mark_processed(self, symbol: str, timestamp: int, action: str) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR IGNORE INTO processed_candles VALUES(?,?,?,?)",
                        (symbol, int(timestamp), action, int(time.time())))

    def _set_mark(self, symbol: str, price: float) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR REPLACE INTO marks VALUES(?,?)", (symbol, float(price)))

    def _marks(self) -> dict:
        with sqlite3.connect(self.db_path) as con:
            return {s: float(p) for s, p in con.execute("SELECT symbol,price FROM marks")}

    def _equity(self) -> float:
        marks = self._marks()
        return self.broker.cash + sum(
            p["quantity"] * marks.get(symbol, p["avg_entry"])
            for symbol, p in self.broker.positions().items())

    def _position_risk(self, position: dict) -> float:
        stop_exit = position["stop_price"] * (1 - SLIPPAGE_RATE)
        entry = position["avg_entry"]
        per_unit = max(0.0, entry - stop_exit + entry * FEE_RATE + stop_exit * FEE_RATE)
        return position["quantity"] * per_unit

    def _snapshot(self, timestamp: int) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR REPLACE INTO equity_snapshots VALUES(?,?,?,?)",
                        (int(timestamp), self._equity(), self.broker.cash,
                         len(self.broker.positions())))

    def _save_status(self, symbol: str, ts: int, row) -> None:
        """Why the bot is (not) trading: latest trend/channel state per symbol, shown on the status page."""
        def num(value):
            return float(value) if pd.notna(value) and math.isfinite(float(value)) else None
        with sqlite3.connect(self.db_path) as con:
            con.execute("INSERT OR REPLACE INTO symbol_status VALUES(?,?,?,?,?,?,?)",
                        (symbol, ts, float(row.close), num(row.EMA200), num(row.ENTRY_CHANNEL),
                         int(row.bars_in_segment), int(bool(row.BUY))))

    # --------------------------------------------------------------- one candle
    def _process_row(self, symbol: str, row) -> dict:
        ts = int(row.timestamp)
        if self._already_processed(symbol, ts):
            return {"symbol": symbol, "timestamp": ts, "action": "DUPLICATE_IGNORED"}
        action = "NO_SIGNAL"
        position = self.broker.positions().get(symbol)
        event_base = f"{symbol}:{ts}"
        price = float(row.close)
        opened_now = False
        self._save_status(symbol, ts, row)
        if position and float(row.low) <= float(position["stop_price"]):
            # Stop-market approximation: a candle that opens through the stop fills at the worse open.
            self.broker.sell(f"{event_base}:STOP", symbol,
                             min(float(row.open), float(position["stop_price"])))
            action = "PAPER_STOP"
        elif position and bool(row.SELL):
            self.broker.sell(f"{event_base}:SELL", symbol, price)
            action = "PAPER_SELL"
        elif not position and bool(row.BUY):
            action = self._try_entry(symbol, row, event_base, price)
            opened_now = action == "PAPER_BUY"
        # Trailing stop from the completed close, for positions that were already open.
        if not opened_now and action == "NO_SIGNAL":
            held = self.broker.positions().get(symbol)
            atr = float(row.ATR14) if pd.notna(row.ATR14) else float("nan")
            if held and atr > 0 and atr == atr:
                update = update_trailing_stop(float(held["stop_price"]), price, atr, ATR_STOP_MULTIPLIER)
                if update.updated:
                    self.broker.update_stop(symbol, update.stop_price)
        self._mark_processed(symbol, ts, action)
        return {"symbol": symbol, "timestamp": ts, "action": action,
                "close": price, "cash": self.broker.cash}

    def _try_entry(self, symbol, row, event_base, price) -> str:
        positions = self.broker.positions()
        if len(positions) >= MAX_OPEN_POSITIONS:
            return "SKIPPED_NO_SLOT"
        atr = row.ATR14
        if pd.isna(atr) or not math.isfinite(float(atr)) or float(atr) <= 0:
            return "NO_SIGNAL"
        equity = self._equity()
        sizing = calculate_position_size(
            equity=equity, available_cash=self.broker.cash, entry_price=price, atr=float(atr),
            risk_pct=MAX_RISK_PER_TRADE, atr_multiplier=ATR_STOP_MULTIPLIER,
            fee_rate=FEE_RATE, slippage_rate=SLIPPAGE_RATE)
        if not sizing.valid or sizing.quantity <= 0:
            return "NO_SIGNAL"
        check = check_portfolio_risk(
            equity=equity,
            open_positions=[{"risk_amount": self._position_risk(p)} for p in positions.values()],
            new_trade_risk=sizing.estimated_risk, max_portfolio_risk=MAX_PORTFOLIO_RISK)
        if not check.allowed:
            return "SKIPPED_PORTFOLIO_RISK"
        self.broker.buy(f"{event_base}:BUY", symbol, price, sizing.quantity, sizing.stop_price)
        return "PAPER_BUY"

    # ----------------------------------------------------------------- cycles
    def _unprocessed_rows(self, symbol: str, signals: pd.DataFrame) -> pd.DataFrame:
        last = self._last_processed_ts(symbol)
        if last is None:                      # first run: observe from the latest closed candle on
            return signals.tail(1)
        return signals[signals.timestamp > last]

    def process_symbol(self, symbol: str, candles: pd.DataFrame) -> dict:
        signals = prepare_breakout_frame(candles, self.timeframe)
        rows = self._unprocessed_rows(symbol, signals)
        if rows.empty:
            return {"symbol": symbol, "timestamp": int(signals.timestamp.iloc[-1]),
                    "action": "DUPLICATE_IGNORED"}
        result = None
        for row in rows.itertuples(index=False):
            self._set_mark(symbol, float(row.close))
            result = self._process_row(symbol, row)
        self._snapshot(int(rows.timestamp.iloc[-1]))
        return result

    def run_once(self, symbols=SYMBOLS) -> list[dict]:
        results, frames = [], {}
        consecutive_failures = 0
        circuit_open = False
        for symbol in symbols:
            try:
                fetch = getattr(self.client, "fetch_closed", None)
                if fetch is not None:
                    candles = retry_call(lambda: fetch(symbol, self.timeframe),
                                         attempts=self.retry_attempts)
                else:  # compatibility with older injected test clients
                    candles = retry_call(lambda: self.client.fetch_closed_4h(symbol),
                                         attempts=self.retry_attempts)
                frames[symbol] = prepare_breakout_frame(candles, self.timeframe)
                consecutive_failures = 0
            except Exception as exc:
                consecutive_failures += 1
                results.append({"symbol": symbol, "action": "DATA_OR_PROCESSING_ERROR",
                                "error": f"{type(exc).__name__}: {exc}"})
                if self.logger:
                    self.logger.exception("symbol_cycle_failed symbol=%s", symbol)
                # Fail closed: after repeated consecutive failures stop requesting more symbols.
                if consecutive_failures >= 3:
                    circuit_open = True
                    if self.logger:
                        self.logger.error("circuit_open consecutive_failures=%s", consecutive_failures)
                    break

        # Catch-up: all unprocessed closed candles of all fetched symbols, in time order.
        events = []
        for order, (symbol, signals) in enumerate(frames.items()):
            rows = self._unprocessed_rows(symbol, signals)
            if rows.empty:
                results.append({"symbol": symbol, "timestamp": int(signals.timestamp.iloc[-1]),
                                "action": "DUPLICATE_IGNORED"})
            for row in rows.itertuples(index=False):
                events.append((int(row.timestamp), order, symbol, row))
        events.sort(key=lambda e: (e[0], e[1]))
        current_ts = None
        for ts, _order, symbol, row in events:
            if ts != current_ts:
                if current_ts is not None:
                    self._snapshot(current_ts)
                current_ts = ts
                for sym, sig in frames.items():     # value every holding at this candle's close
                    match = sig[sig.timestamp == ts]
                    if not match.empty:
                        self._set_mark(sym, float(match.close.iloc[0]))
            result = self._process_row(symbol, row)
            results.append(result)
            if self.logger:
                self.logger.info("symbol_cycle %s", result)
        if current_ts is not None:
            self._snapshot(current_ts)
        if circuit_open:
            results.append({"action": "CIRCUIT_OPEN",
                            "reason": "three consecutive symbol failures; cycle halted"})
        return results


def main():
    parser = argparse.ArgumentParser(description="MABOT read-only market data + paper execution")
    parser.add_argument("--db", default="results/mabot_paper.sqlite3")
    parser.add_argument("--once", action="store_true", help="Run one polling cycle")
    parser.add_argument("--interval", type=int, default=900, help="Polling interval seconds")
    parser.add_argument("--timeframe", choices=("1h", "4h", "1d"), default="4h")
    parser.add_argument("--log-file", default="results/logs/paper_runner.log")
    parser.add_argument("--retry-attempts", type=int, default=3)
    args = parser.parse_args()
    if args.interval < 10:
        parser.error("--interval must be at least 10 seconds")
    logger = configure_logging(args.log_file)
    runner = PaperSignalRunner(args.db, retry_attempts=args.retry_attempts,
                               logger=logger, timeframe=args.timeframe)
    print(f"MABOT PAPER RUNNER | {args.timeframe} | PUBLIC READ-ONLY DATA | REAL ORDERS DISABLED")
    while True:
        try:
            for result in runner.run_once():
                print(result)
        except Exception as exc:
            # Fail closed: no signal execution on data or processing errors.
            logger.exception("cycle_error")
            print(f"CYCLE_ERROR: {type(exc).__name__}: {exc}")
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
