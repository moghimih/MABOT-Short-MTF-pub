import pandas as pd
import numpy as np
from pathlib import Path

# ==========================================
# MABOT - BACKTEST ENGINE V1
# SPOT / LONG ONLY / NO REAL TRADING
# ==========================================

INITIAL_CAPITAL = 100.0

FEE_RATE = 0.002
SLIPPAGE_RATE = 0.0005

TEST_RATIO = 0.30

FILES = {
    "BTC": "btcusdt_history_extended.csv",
    "ETH": "ethusdt_history_extended.csv",
    "ZEC": "zecusdt_history_extended.csv",
    "XRP": "xrpusdt_history_extended.csv"
}


def load_data(filename):

    df = pd.read_csv(filename)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        unit="s",
        utc=True
    )

    df = df.sort_values("timestamp").reset_index(drop=True)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col])

    return df


def calculate_indicators(df):

    df["EMA20"] = df["close"].ewm(
        span=20,
        adjust=False
    ).mean()

    df["EMA50"] = df["close"].ewm(
        span=50,
        adjust=False
    ).mean()

    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1/14,
        adjust=False,
        min_periods=14
    ).mean()

    avg_loss = loss.ewm(
        alpha=1/14,
        adjust=False,
        min_periods=14
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    df["RSI"] = 100 - (100 / (1 + rs))

    df["BUY_SIGNAL"] = (
        (df["EMA20"] > df["EMA50"]) &
        (df["RSI"] > 50)
    )

    df["SELL_SIGNAL"] = (
        (df["EMA20"] < df["EMA50"]) |
        (df["RSI"] < 45)
    )

    return df


def run_backtest(df):

    split = int(len(df) * (1 - TEST_RATIO))

    # فقط بخش پایانی برای ارزیابی
    test_start = split

    cash = INITIAL_CAPITAL
    quantity = 0.0

    trades = []
    equity_curve = []

    position = False
    entry_price = 0.0

    cost = FEE_RATE + SLIPPAGE_RATE

    for i in range(test_start, len(df)):

        row = df.iloc[i]
        previous = df.iloc[i - 1]

        # سیگنال کندل قبلی، اجرا در Open کندل فعلی
        price = float(row["open"])

        buy_signal = bool(previous["BUY_SIGNAL"])
        sell_signal = bool(previous["SELL_SIGNAL"])

        if not position and buy_signal:

            execution_price = price * (1 + SLIPPAGE_RATE)

            quantity = cash / (
                execution_price * (1 + FEE_RATE)
            )

            cash = 0.0
            entry_price = execution_price

            position = True

            trades.append({
                "type": "BUY",
                "price": execution_price,
                "time": row["timestamp"]
            })

        elif position and sell_signal:

            execution_price = price * (1 - SLIPPAGE_RATE)

            cash = (
                quantity *
                execution_price *
                (1 - FEE_RATE)
            )

            profit = (
                cash / INITIAL_CAPITAL - 1
            ) * 100

            trades.append({
                "type": "SELL",
                "price": execution_price,
                "time": row["timestamp"],
                "profit_vs_initial_pct": profit
            })

            quantity = 0.0
            position = False

        equity = cash + quantity * float(row["close"])

        equity_curve.append({
            "timestamp": row["timestamp"],
            "equity": equity
        })

    # بستن موقعیت باز در انتهای آزمایش
    if position:

        final_price = float(df.iloc[-1]["close"])

        execution_price = final_price * (1 - SLIPPAGE_RATE)

        cash = (
            quantity *
            execution_price *
            (1 - FEE_RATE)
        )

        quantity = 0.0
        position = False

        trades.append({
            "type": "FINAL_EXIT",
            "price": execution_price,
            "time": df.iloc[-1]["timestamp"]
        })

    final_capital = cash

    # محاسبه منحنی سرمایه
    equity_values = [
        item["equity"] for item in equity_curve
    ]

    if equity_values:

        equity_values[-1] = final_capital

        series = pd.Series(equity_values)

        peak = series.cummax()

        drawdown = (
            (series - peak) / peak
        ) * 100

        max_drawdown = drawdown.min()

    else:
        max_drawdown = 0

    sell_trades = [
        t for t in trades
        if t["type"] == "SELL"
    ]

    completed = len(sell_trades)

    profitable = sum(
        1 for t in sell_trades
        if t["price"] > 0
    )

    # محاسبه سود معاملات بر اساس جفت ورود و خروج
    trade_profits = []

    for j in range(0, len(trades) - 1):

        if (
            trades[j]["type"] == "BUY"
            and trades[j + 1]["type"] in ["SELL", "FINAL_EXIT"]
        ):

            buy_price = trades[j]["price"]
            sell_price = trades[j + 1]["price"]

            net_return = (
                sell_price * (1 - FEE_RATE)
                /
                (buy_price * (1 + FEE_RATE))
                - 1
            ) * 100

            trade_profits.append(net_return)

    winning_trades = sum(
        1 for p in trade_profits if p > 0
    )

    win_rate = (
        winning_trades / len(trade_profits) * 100
        if trade_profits else 0
    )

    return {
        "initial": INITIAL_CAPITAL,
        "final": final_capital,
        "return_pct": (
            final_capital / INITIAL_CAPITAL - 1
        ) * 100,
        "trades": len(trade_profits),
        "win_rate": win_rate,
        "max_drawdown": max_drawdown
    }


def main():

    print("=" * 60)
    print("MABOT - BACKTEST ENGINE V1")
    print("REAL TRADING: DISABLED")
    print("=" * 60)

    for symbol, filename in FILES.items():

        print(f"\nAnalyzing {symbol}...")

        if not Path(filename).exists():
            print("File not found:", filename)
            continue

        df = load_data(filename)

        df = calculate_indicators(df)

        result = run_backtest(df)

        print("-" * 40)

        print("Test candles:", int(len(df) * TEST_RATIO))

        print(
            "Initial capital:",
            round(result["initial"], 2)
        )

        print(
            "Final capital:",
            round(result["final"], 2)
        )

        print(
            "Return:",
            round(result["return_pct"], 2), "%"
        )

        print(
            "Completed trades:",
            result["trades"]
        )

        print(
            "Win rate:",
            round(result["win_rate"], 2), "%"
        )

        print(
            "Maximum drawdown:",
            round(result["max_drawdown"], 2), "%"
        )

        print("-" * 40)


if __name__ == "__main__":
    main()