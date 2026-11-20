"""Independent short-only 1m/5m/15m paper strategy. No exchange order endpoints."""
from __future__ import annotations

import math
import sqlite3
import time
from pathlib import Path

import pandas as pd

from config.settings import FEE_RATE, INITIAL_CAPITAL, SLIPPAGE_RATE, SYMBOLS
from paper_trading.market_data import NobitexPublicDataClient
from paper_trading.ops import retry_call

TF = {"1m": ("1", 60), "5m": ("5", 300), "15m": ("15", 900)}
ATR_MULT = 2.5
RISK_PER_TRADE = 0.005       # 0.5% of equity
MAX_PORTFOLIO_RISK = 0.01    # 1% of equity
MAX_NOTIONAL_FRACTION = 0.20 # unlevered notional cap per position
MAX_POSITIONS = 2


def _validate_candles(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    if tf not in TF:
        raise ValueError(f"Unsupported timeframe: {tf}")
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing candle fields: {sorted(missing)}")
    out = df.copy().sort_values("timestamp").drop_duplicates("timestamp", keep="last").reset_index(drop=True)
    for c in ("timestamp", "open", "high", "low", "close", "volume"):
        out[c] = pd.to_numeric(out[c], errors="raise")
    if out.empty or out[list(required)].isna().any().any():
        raise ValueError("Empty or invalid candles")
    if (out[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC values must be positive")
    if ((out.high < out.low) | (out.high < out.open) | (out.high < out.close) |
            (out.low > out.open) | (out.low > out.close)).any():
        raise ValueError("Invalid OHLC relationships")
    seconds = TF[tf][1]
    gaps = out.timestamp.diff().fillna(seconds).ne(seconds)
    out["segment"] = gaps.cumsum().astype(int) - 1
    return out


def _indicators(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    out = _validate_candles(df, tf)
    pieces = []
    for _, part in out.groupby("segment", sort=False):
        p = part.copy()
        p["ema20"] = p.close.ewm(span=20, adjust=False).mean()
        p["ema50"] = p.close.ewm(span=50, adjust=False).mean()
        p["ema200"] = p.close.ewm(span=200, adjust=False).mean()
        prev_close = p.close.shift(1)
        tr = pd.concat([(p.high-p.low), (p.high-prev_close).abs(), (p.low-prev_close).abs()], axis=1).max(axis=1)
        p["atr14"] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
        p["prior_low20"] = p.low.shift(1).rolling(20, min_periods=20).min()
        p["prior_high10"] = p.high.shift(1).rolling(10, min_periods=10).max()
        p["bars"] = range(1, len(p)+1)
        pieces.append(p)
    return pd.concat(pieces, ignore_index=True)


def evaluate_short_signal(c1: pd.DataFrame, c5: pd.DataFrame, c15: pd.DataFrame) -> dict:
    """Evaluate only fully closed and time-aligned candles at the latest 5m close."""
    one = _indicators(c1, "1m")
    five = _indicators(c5, "5m")
    fifteen = _indicators(c15, "15m")
    if len(five) < 2:
        return {"ready": False, "reason": "کمبود کندل ۵ دقیقه"}
    decision_end = int(five.timestamp.iloc[-1]) + 300
    # Require the selected 5m candle itself to be closed by wall-clock filtering upstream.
    one = one[one.timestamp + 60 <= decision_end]
    fifteen = fifteen[fifteen.timestamp + 900 <= decision_end]
    if one.empty or fifteen.empty:
        return {"ready": False, "reason": "کندل بسته‌شده هم‌زمان در دسترس نیست"}
    r1, r5 = one.iloc[-1], five.iloc[-1]
    r15 = fifteen.iloc[-1]
    if int(r5.timestamp) + 300 != decision_end:
        return {"ready": False, "reason": "کندل ۵ دقیقه معتبر نیست"}
    if int(r1.timestamp) + 60 != decision_end:
        return {"ready": False, "reason": "کندل ۱ دقیقه‌ای آخرین کندل بازه ۵دقیقه نیست"}
    if int(r15.timestamp) + 900 > decision_end:
        return {"ready": False, "reason": "تأیید ۱۵ دقیقه‌ای هنوز بسته نشده"}
    if decision_end - (int(r15.timestamp) + 900) >= 900:
        return {"ready": False, "reason": "داده ۱۵ دقیقه‌ای قدیمی یا دارای شکاف است"}
    if (int(r15.bars) < 200 or int(r5.bars) < 50 or int(r1.bars) < 20
            or pd.isna(r15.ema200) or pd.isna(r5.ema50) or pd.isna(r1.ema20)
            or pd.isna(r5.prior_low20) or pd.isna(r5.atr14)):
        return {"ready": False, "reason": "در حال گرم‌شدن اندیکاتورها (۲۰۰ کندل ۱۵دقیقه‌ای لازم است)"}
    trend_bearish = bool(r15.close < r15.ema200 and r15.ema20 < r15.ema50)
    breakdown = bool(r5.close < r5.prior_low20 and r5.close < r5.ema50)
    confirm_1m = bool(r1.close < r1.ema20 and r1.close < r1.open)
    exit_signal = bool(r5.close > r5.prior_high10) if pd.notna(r5.prior_high10) else False
    ready = all(pd.notna(x) for x in (r5.atr14, r15.ema200, r1.ema20))
    return {
        "ready": ready, "timestamp": decision_end - 300,
        "trend_15m": trend_bearish, "breakdown_5m": breakdown,
        "confirm_1m": confirm_1m, "short_signal": bool(ready and trend_bearish and breakdown and confirm_1m),
        "cover_signal": bool(ready and (not trend_bearish or exit_signal)),
        "price": float(r5.close), "atr": float(r5.atr14),
        "stop": float(r5.close + ATR_MULT * r5.atr14),
        "status": "تأیید سه‌تایم‌فریمی" if ready and trend_bearish and breakdown and confirm_1m else "عدم تطابق شرایط",
        "reason": "15m trend / 5m breakdown / 1m confirmation",
    }


class ShortPaperBroker:
    """Cash-equity short simulator. Short proceeds are not treated as free cash."""
    def __init__(self, db_path, initial_cash=INITIAL_CAPITAL, fee_rate=FEE_RATE, slippage_rate=SLIPPAGE_RATE):
        self.db_path = str(db_path)
        self.fee_rate, self.slippage_rate = float(fee_rate), float(slippage_rate)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS account (id INTEGER PRIMARY KEY CHECK(id=1), cash REAL NOT NULL)")
            con.execute("INSERT OR IGNORE INTO account VALUES(1,?)", (float(initial_cash),))
            con.execute("CREATE TABLE IF NOT EXISTS positions (symbol TEXT PRIMARY KEY, quantity REAL NOT NULL, entry REAL NOT NULL, stop REAL NOT NULL, opened_at INTEGER NOT NULL)")
            con.execute("CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, side TEXT, symbol TEXT, quantity REAL, price REAL, fee REAL, pnl REAL, timestamp INTEGER)")
    def _connect(self): return sqlite3.connect(self.db_path, timeout=30)
    @property
    def cash(self):
        with self._connect() as c: return float(c.execute("SELECT cash FROM account WHERE id=1").fetchone()[0])
    def positions(self):
        with self._connect() as c:
            rows=c.execute("SELECT symbol,quantity,entry,stop,opened_at FROM positions").fetchall()
        return {r[0]: {"quantity":r[1],"entry":r[2],"stop":r[3],"opened_at":r[4]} for r in rows}
    def events(self):
        with self._connect() as c:
            rows=c.execute("SELECT event_id,side,symbol,quantity,price,fee,pnl,timestamp FROM events ORDER BY rowid DESC LIMIT 30").fetchall()
        return rows
    def equity(self, marks):
        pos=self.positions()
        return self.cash + sum((p["entry"]-float(marks.get(s,p["entry"]))) * p["quantity"] for s,p in pos.items())
    def open_short(self, event_id, symbol, ref_price, qty, stop, ts):
        if not all(math.isfinite(float(x)) and float(x)>0 for x in (ref_price,qty,stop)) or stop<=ref_price:
            raise ValueError("Invalid short order or stop")
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT 1 FROM events WHERE event_id=?",(event_id,)).fetchone(): return False
            if c.execute("SELECT 1 FROM positions WHERE symbol=?",(symbol,)).fetchone(): return False
            fill=ref_price*(1-self.slippage_rate); fee=fill*qty*self.fee_rate
            cash=float(c.execute("SELECT cash FROM account WHERE id=1").fetchone()[0])-fee
            c.execute("UPDATE account SET cash=? WHERE id=1",(cash,))
            c.execute("INSERT INTO positions VALUES(?,?,?,?,?)",(symbol,qty,fill,stop,int(ts)))
            c.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?)",(event_id,"SHORT_OPEN",symbol,qty,fill,fee,-fee,int(ts)))
        return True
    def cover(self,event_id,symbol,ref_price,ts,reason="COVER"):
        with self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT 1 FROM events WHERE event_id=?",(event_id,)).fetchone(): return False
            row=c.execute("SELECT quantity,entry FROM positions WHERE symbol=?",(symbol,)).fetchone()
            if not row: return False
            qty,entry=map(float,row); fill=ref_price*(1+self.slippage_rate)
            gross=(entry-fill)*qty; fee=fill*qty*self.fee_rate; net=gross-fee
            cash=float(c.execute("SELECT cash FROM account WHERE id=1").fetchone()[0])+net
            c.execute("UPDATE account SET cash=? WHERE id=1",(cash,))
            c.execute("DELETE FROM positions WHERE symbol=?",(symbol,))
            c.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?)",(event_id,reason,symbol,qty,fill,fee,net,int(ts)))
        return True
    def update_stop(self,symbol,new_stop):
        with self._connect() as c:
            c.execute("UPDATE positions SET stop=? WHERE symbol=? AND stop> ?",(float(new_stop),symbol,float(new_stop)))


class ShortMTFRunner:
    def __init__(self, db_path="results/short_mtf.sqlite3", client=None, logger=None):
        self.db_path=str(db_path); self.client=client or NobitexPublicDataClient(); self.logger=logger
        self.broker=ShortPaperBroker(self.db_path)
        with sqlite3.connect(self.db_path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS processed (symbol TEXT, timestamp INTEGER, action TEXT, PRIMARY KEY(symbol,timestamp))")
            c.execute("CREATE TABLE IF NOT EXISTS marks (symbol TEXT PRIMARY KEY, price REAL)")
            c.execute("CREATE TABLE IF NOT EXISTS status (symbol TEXT PRIMARY KEY, timestamp INTEGER, price REAL, trend15 INTEGER, breakdown5 INTEGER, confirm1 INTEGER, state TEXT, reason TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS snapshots (timestamp INTEGER PRIMARY KEY, equity REAL, cash REAL, positions INTEGER)")
    def _already(self,s,ts):
        with sqlite3.connect(self.db_path) as c: return c.execute("SELECT 1 FROM processed WHERE symbol=? AND timestamp=?",(s,int(ts))).fetchone() is not None
    def _mark(self,s,p):
        with sqlite3.connect(self.db_path) as c: c.execute("INSERT OR REPLACE INTO marks VALUES(?,?)",(s,float(p)))
    def _marks(self):
        with sqlite3.connect(self.db_path) as c: return dict(c.execute("SELECT symbol,price FROM marks"))
    def _status(self,s,ts,sig):
        with sqlite3.connect(self.db_path) as c:
            c.execute("INSERT OR REPLACE INTO status VALUES(?,?,?,?,?,?,?,?)",(s,int(ts),sig.get("price"),int(sig.get("trend_15m",False)),int(sig.get("breakdown_5m",False)),int(sig.get("confirm_1m",False)),sig.get("status",sig.get("reason","-")),sig.get("reason","-")))
    def run_once(self,symbols=SYMBOLS):
        out=[]
        for symbol in symbols:
            try:
                frames={tf:retry_call(lambda tf=tf:self.client.fetch_closed(symbol,tf),attempts=3) for tf in ("1m","5m","15m")}
                sig=evaluate_short_signal(frames["1m"],frames["5m"],frames["15m"])
                if not sig.get("ready"):
                    latest=frames["5m"].iloc[-1]
                    self._status(symbol,int(latest.timestamp),{"price":float(latest.close),"reason":sig.get("reason"),"status":sig.get("reason")})
                    out.append({"symbol":symbol,"action":"WAIT_DATA","reason":sig.get("reason")}); continue
                ts=int(sig["timestamp"]); price=float(sig["price"]); self._mark(symbol,price); self._status(symbol,ts,sig)
                if self._already(symbol,ts):
                    out.append({"symbol":symbol,"timestamp":ts,"action":"DUPLICATE_IGNORED"}); continue
                pos=self.broker.positions().get(symbol); action="NO_SIGNAL"
                if pos:
                    stop_hit=float(frames["5m"].iloc[-1].high)>=float(pos["stop"])
                    if stop_hit:
                        self.broker.cover(f"{symbol}:{ts}:STOP",symbol,max(float(frames["5m"].iloc[-1].open),float(pos["stop"])),ts,"SHORT_STOP")
                        action="PAPER_SHORT_STOP"
                    elif sig.get("cover_signal"):
                        self.broker.cover(f"{symbol}:{ts}:COVER",symbol,price,ts,"SHORT_COVER")
                        action="PAPER_SHORT_COVER"
                    else:
                        new_stop=price+ATR_MULT*float(sig["atr"])
                        if new_stop>0: self.broker.update_stop(symbol,new_stop)
                elif sig.get("short_signal") and len(self.broker.positions())<MAX_POSITIONS:
                    equity=self.broker.equity(self._marks()); risk_budget=equity*RISK_PER_TRADE
                    stop=float(sig["stop"]); estimated_entry=price*(1-self.broker.slippage_rate)
                    per_unit=(stop-estimated_entry)+price*(self.broker.fee_rate*2+self.broker.slippage_rate*2)
                    qty=min(risk_budget/max(per_unit,1e-12), equity*MAX_NOTIONAL_FRACTION/price)
                    open_risk=sum(p["quantity"]*(p["stop"]-p["entry"]+p["entry"]*(self.broker.fee_rate*2+self.broker.slippage_rate*2)) for p in self.broker.positions().values())
                    if qty>0 and open_risk+qty*per_unit<=equity*MAX_PORTFOLIO_RISK:
                        if self.broker.open_short(f"{symbol}:{ts}:SHORT",symbol,price,qty,stop,ts): action="PAPER_SHORT_OPEN"
                with sqlite3.connect(self.db_path) as c: c.execute("INSERT OR IGNORE INTO processed VALUES(?,?,?)",(symbol,ts,action))
                with sqlite3.connect(self.db_path) as c: c.execute("INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?)",(ts,self.broker.equity(self._marks()),self.broker.cash,len(self.broker.positions())))
                out.append({"symbol":symbol,"timestamp":ts,"action":action,"price":price,"equity":round(self.broker.equity(self._marks()),4),"status":sig.get("status")})
            except Exception as exc:
                if self.logger: self.logger.exception("short_mtf_symbol_error %s",symbol)
                out.append({"symbol":symbol,"action":"DATA_OR_PROCESSING_ERROR","error":f"{type(exc).__name__}: {exc}"})
        return out
