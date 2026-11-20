# MABOT - BACKTEST V3 (timeframe comparison)  |  SPOT / LONG ONLY  |  REAL TRADING: DISABLED
# Same signal and same costs as backtest_v2.py, but the hourly data can be resampled to 4h / 1d
# to see how much of the loss comes from trading too often.
# Run next to the *_history_extended.csv files:  python backtest_v3_timeframes_fixed.py
import numpy as np
import pandas as pd

INITIAL_CAPITAL = 100.0
FEE_RATE = 0.002          # CHECK against your real Nobitex fee tier
SLIPPAGE_RATE = 0.0005
TEST_RATIO = 0.30
WARMUP = 60               # candles skipped at the start so EMA/RSI are warmed up
FILES = {"BTC": "btcusdt_history_extended.csv", "ETH": "ethusdt_history_extended.csv",
         "ZEC": "zecusdt_history_extended.csv", "XRP": "xrpusdt_history_extended.csv"}
TIMEFRAMES = {"1h": 1, "4h": 4, "1d": 24}      # hours per candle


def load(filename, hours):
    df = pd.read_csv(filename)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df = df.sort_values("timestamp").set_index("timestamp")[["open", "high", "low", "close", "volume"]]
    if hours > 1:
        g = df.resample(f"{hours}h", label="left", closed="left")
        out = g.agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        out["n"] = g["close"].count()
        df = out[out["n"] == hours].drop(columns="n")        # drop incomplete bins
    return df.reset_index()


def add_signals(df):
    c = df["close"]
    df["EMA20"] = c.ewm(span=20, adjust=False).mean()
    df["EMA50"] = c.ewm(span=50, adjust=False).mean()
    d = c.diff()
    ag = d.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    al = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rsi = 100 - 100 / (1 + ag / al.replace(0, np.nan))
    df["RSI"] = rsi.mask((al == 0) & (ag > 0), 100).mask((al == 0) & (ag == 0), 50)
    df["BUY"] = ((df["EMA20"] > df["EMA50"]) & (df["RSI"] > 50)).fillna(False)
    df["SELL"] = ((df["EMA20"] < df["EMA50"]) | (df["RSI"] < 45)).fillna(False)
    return df


def backtest(df, start, end, fee=FEE_RATE, slip=SLIPPAGE_RATE):
    cash, qty, pos, invested = INITIAL_CAPITAL, 0.0, False, 0.0
    trades, equity = [], [INITIAL_CAPITAL]
    for i in range(start, end):
        op, cl = df["open"].iat[i], df["close"].iat[i]
        if not pos and df["BUY"].iat[i - 1]:               # signal from previous candle, fill at this open
            invested, qty = cash, cash / (op * (1 + slip) * (1 + fee))
            cash, pos = 0.0, True
        elif pos and df["SELL"].iat[i - 1]:
            cash = qty * op * (1 - slip) * (1 - fee)
            trades.append((cash / invested - 1) * 100)
            qty, pos = 0.0, False
        equity.append(qty * cl * (1 - slip) * (1 - fee) if pos else cash)
    if pos:
        # Close any remaining position at the final candle close.
        final_exit_price = df["close"].iat[end - 1] * (1 - slip)
        cash = qty * final_exit_price * (1 - fee)

        # Include this forced final exit in trade statistics as well.
        final_trade_return_pct = (cash / invested - 1) * 100
        trades.append(final_trade_return_pct)
        equity[-1] = cash
    eq = np.array(equity)
    return {"ret": (cash / INITIAL_CAPITAL - 1) * 100,
            "dd": (eq / np.maximum.accumulate(eq) - 1).min() * 100,
            "trades": len(trades), "win": (np.array(trades) > 0).mean() * 100 if trades else 0.0,
            "trade_returns": trades}


def buy_hold(df, start, end, fee=FEE_RATE, slip=SLIPPAGE_RATE):
    e = df["open"].iat[start] * (1 + slip)
    x = df["close"].iat[end - 1] * (1 - slip)
    return (x / e * (1 - fee) / (1 + fee) - 1) * 100


def main():
    print("=" * 72)
    print("MABOT - BACKTEST V3 (TIMEFRAME COMPARISON)   REAL TRADING: DISABLED")
    print(f"fee={FEE_RATE*100:.2f}%  slippage={SLIPPAGE_RATE*100:.3f}%  per side")
    print("=" * 72)
    for tf, hours in TIMEFRAMES.items():
        print(f"\n##### TIMEFRAME {tf} #####")
        for period in ("TEST", "TRAIN"):
            rows, pooled = [], []
            for sym, fn in FILES.items():
                df = add_signals(load(fn, hours))
                split = int(len(df) * (1 - TEST_RATIO))
                a, b = (split, len(df)) if period == "TEST" else (WARMUP, split)
                r = backtest(df, a, b)
                pooled += r["trade_returns"]
                rows.append((sym, r["ret"], buy_hold(df, a, b), r["dd"], r["trades"], r["win"]))
            print(f"\n{period}:   market   return%   buy&hold%   maxDD%   trades   win%")
            for s, ret, bh, dd, n, w in rows:
                print(f"        {s:6s} {ret:8.2f} {bh:10.2f} {dd:9.2f} {n:8d} {w:6.1f}")
            p = np.array(pooled)
            if len(p) > 1:
                t = p.mean() / (p.std(ddof=1) / np.sqrt(len(p)))
                print(f"        avg return {np.mean([r[1] for r in rows]):.2f}% | pooled trades {len(p)} | "
                      f"mean/trade {p.mean():.2f}% | t-stat {t:.2f}")
    print("\nNOTE: t-stat is descriptive only; small samples and dependent trades limit inference.")
    print("REAL TRADING: DISABLED")


if __name__ == "__main__":
    main()
