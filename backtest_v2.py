import pandas as pd
import numpy as np
from pathlib import Path

# =====================================================
# MABOT - BACKTEST ENGINE V2
# SPOT / LONG ONLY
# REAL TRADING: DISABLED
# =====================================================

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


# -----------------------------------------------------
# LOAD DATA
# -----------------------------------------------------

def load_data(filename):

    df = pd.read_csv(filename)

    if pd.api.types.is_numeric_dtype(df["timestamp"]):
        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            unit="s",
            utc=True
        )
    else:
        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            utc=True
        )

    df = df.sort_values("timestamp").reset_index(drop=True)

    required = [
        "open", "high", "low", "close", "volume"
    ]

    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df[required].isnull().any().any():
        raise ValueError("Missing or invalid market values.")

    if df["timestamp"].duplicated().any():
        raise ValueError("Duplicate timestamps found.")

    if len(df) < 200:
        raise ValueError("Not enough historical candles.")

    return df


# -----------------------------------------------------
# TECHNICAL INDICATORS
# -----------------------------------------------------

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
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    rsi = rsi.mask(
        (avg_loss == 0) & (avg_gain > 0),
        100
    )

    rsi = rsi.mask(
        (avg_loss == 0) & (avg_gain == 0),
        50
    )

    df["RSI"] = rsi

    # Entry condition
    df["BUY_SIGNAL"] = (
        (df["EMA20"] > df["EMA50"]) &
        (df["RSI"] > 50)
    ).fillna(False)

    # Exit condition
    df["SELL_SIGNAL"] = (
        (df["EMA20"] < df["EMA50"]) |
        (df["RSI"] < 45)
    ).fillna(False)

    return df


# -----------------------------------------------------
# BUY & HOLD BENCHMARK
# -----------------------------------------------------

def calculate_buy_hold(test):

    start_price = float(test.iloc[0]["open"])
    end_price = float(test.iloc[-1]["close"])

    buy_price = start_price * (1 + SLIPPAGE_RATE)
    sell_price = end_price * (1 - SLIPPAGE_RATE)

    quantity = INITIAL_CAPITAL / (
        buy_price * (1 + FEE_RATE)
    )

    final_value = (
        quantity *
        sell_price *
        (1 - FEE_RATE)
    )

    return {
        "final": final_value,
        "return_pct": (
            final_value / INITIAL_CAPITAL - 1
        ) * 100
    }


# -----------------------------------------------------
# BACKTEST
# -----------------------------------------------------

def run_backtest(df, symbol):

    split = int(len(df) * (1 - TEST_RATIO))

    test = df.iloc[split:].reset_index(drop=True)

    if len(test) < 2:
        raise ValueError("Test period is too short.")

    cash = INITIAL_CAPITAL
    quantity = 0.0

    position = False
    entry_data = None

    trades = []
    equity_rows = []

    position_bars = 0

    # Initial equity point
    equity_rows.append({
        "symbol": symbol,
        "timestamp": test.iloc[0]["timestamp"],
        "equity": INITIAL_CAPITAL,
        "position": False
    })

    for i in range(len(test)):

        row = test.iloc[i]

        previous = df.iloc[split + i - 1]

        open_price = float(row["open"])
        close_price = float(row["close"])

        buy_signal = bool(previous["BUY_SIGNAL"])
        sell_signal = bool(previous["SELL_SIGNAL"])

        # ---------------- BUY ----------------

        if not position and buy_signal:

            capital_at_entry = cash

            entry_price = open_price * (
                1 + SLIPPAGE_RATE
            )

            quantity = cash / (
                entry_price * (1 + FEE_RATE)
            )

            entry_fee = (
                quantity * entry_price * FEE_RATE
            )

            cash = 0.0
            position = True

            entry_data = {
                "entry_time": row["timestamp"],
                "entry_price": entry_price,
                "entry_fee": entry_fee,
                "invested_capital": capital_at_entry,
                "quantity": quantity
            }

        # ---------------- SELL ----------------

        elif position and sell_signal:

            exit_price = open_price * (
                1 - SLIPPAGE_RATE
            )

            exit_fee = (
                quantity * exit_price * FEE_RATE
            )

            proceeds = (
                quantity * exit_price * (1 - FEE_RATE)
            )

            pnl = proceeds - entry_data["invested_capital"]

            return_pct = (
                pnl / entry_data["invested_capital"]
            ) * 100

            holding_hours = (
                row["timestamp"] -
                entry_data["entry_time"]
            ).total_seconds() / 3600

            trades.append({
                "symbol": symbol,
                "entry_time": entry_data["entry_time"],
                "exit_time": row["timestamp"],
                "entry_price": entry_data["entry_price"],
                "exit_price": exit_price,
                "quantity": quantity,
                "entry_fee": entry_data["entry_fee"],
                "exit_fee": exit_fee,
                "invested_capital": entry_data["invested_capital"],
                "exit_value": proceeds,
                "net_pnl": pnl,
                "net_return_pct": return_pct,
                "holding_hours": holding_hours,
                "exit_reason": "SELL_SIGNAL"
            })

            cash = proceeds
            quantity = 0.0
            position = False
            entry_data = None

        # ---------------- EQUITY ----------------

        if position:

            position_bars += 1

            estimated_exit_price = close_price * (
                1 - SLIPPAGE_RATE
            )

            equity = (
                quantity *
                estimated_exit_price *
                (1 - FEE_RATE)
            )

        else:
            equity = cash

        equity_rows.append({
            "symbol": symbol,
            "timestamp": row["timestamp"],
            "equity": equity,
            "position": position
        })

    # ---------------- FINAL EXIT ----------------

    if position:

        last_row = test.iloc[-1]

        exit_price = float(last_row["close"]) * (
            1 - SLIPPAGE_RATE
        )

        exit_fee = quantity * exit_price * FEE_RATE

        proceeds = (
            quantity * exit_price * (1 - FEE_RATE)
        )

        pnl = proceeds - entry_data["invested_capital"]

        return_pct = (
            pnl / entry_data["invested_capital"]
        ) * 100

        holding_hours = (
            last_row["timestamp"] -
            entry_data["entry_time"]
        ).total_seconds() / 3600

        trades.append({
            "symbol": symbol,
            "entry_time": entry_data["entry_time"],
            "exit_time": last_row["timestamp"],
            "entry_price": entry_data["entry_price"],
            "exit_price": exit_price,
            "quantity": quantity,
            "entry_fee": entry_data["entry_fee"],
            "exit_fee": exit_fee,
            "invested_capital": entry_data["invested_capital"],
            "exit_value": proceeds,
            "net_pnl": pnl,
            "net_return_pct": return_pct,
            "holding_hours": holding_hours,
            "exit_reason": "END_OF_TEST"
        })

        cash = proceeds
        quantity = 0.0
        position = False

        equity_rows[-1]["equity"] = cash
        equity_rows[-1]["position"] = False

    final_capital = cash

    # ---------------- METRICS ----------------

    equity_df = pd.DataFrame(equity_rows)

    equity_series = equity_df["equity"]

    peak = equity_series.cummax()

    drawdown = (
        (equity_series - peak) / peak
    ) * 100

    max_drawdown = float(drawdown.min())

    trades_df = pd.DataFrame(trades)

    total_trades = len(trades_df)

    if total_trades > 0:

        winning_trades = trades_df[
            trades_df["net_pnl"] > 0
        ]

        losing_trades = trades_df[
            trades_df["net_pnl"] < 0
        ]

        win_rate = (
            len(winning_trades) / total_trades
        ) * 100

        gross_profit = winning_trades["net_pnl"].sum()
        gross_loss = abs(losing_trades["net_pnl"].sum())

        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = float("inf")
        else:
            profit_factor = 0.0

        average_trade = trades_df["net_pnl"].mean()

    else:
        win_rate = 0.0
        profit_factor = 0.0
        average_trade = 0.0

    benchmark = calculate_buy_hold(test)

    exposure_pct = (
        position_bars / len(test)
    ) * 100

    result = {
        "symbol": symbol,
        "test_candles": len(test),
        "initial_capital": INITIAL_CAPITAL,
        "final_capital": final_capital,
        "net_profit": final_capital - INITIAL_CAPITAL,
        "return_pct": (
            final_capital / INITIAL_CAPITAL - 1
        ) * 100,
        "trades": total_trades,
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "average_trade_pnl": average_trade,
        "max_drawdown_pct": max_drawdown,
        "exposure_pct": exposure_pct,
        "buy_hold_return_pct": benchmark["return_pct"],
        "outperformance_pct": (
            final_capital / INITIAL_CAPITAL -
            benchmark["final"] / INITIAL_CAPITAL
        ) * 100
    }

    return result, trades_df, equity_df


# -----------------------------------------------------
# MAIN
# -----------------------------------------------------

def main():

    print("=" * 65)
    print("MABOT - BACKTEST ENGINE V2")
    print("REAL TRADING: DISABLED")
    print("=" * 65)

    all_results = []
    all_trades = []
    all_equity = []

    for symbol, filename in FILES.items():

        print(f"\nAnalyzing {symbol}...")

        if not Path(filename).exists():
            print("ERROR: File not found:", filename)
            continue

        try:

            df = load_data(filename)

            df = calculate_indicators(df)

            result, trades, equity = run_backtest(
                df,
                symbol
            )

            all_results.append(result)

            if not trades.empty:
                all_trades.append(trades)

            all_equity.append(equity)

            print("-" * 45)
            print("Test candles:", result["test_candles"])
            print("Initial capital:", round(result["initial_capital"], 2))
            print("Final capital:", round(result["final_capital"], 2))
            print("Net profit:", round(result["net_profit"], 2))
            print("Return:", round(result["return_pct"], 2), "%")
            print("Completed trades:", result["trades"])
            print("Win rate:", round(result["win_rate_pct"], 2), "%")
            print("Profit factor:", round(result["profit_factor"], 3))
            print("Average trade PnL:", round(result["average_trade_pnl"], 3))
            print("Maximum drawdown:", round(result["max_drawdown_pct"], 2), "%")
            print("Market exposure:", round(result["exposure_pct"], 2), "%")
            print("Buy & Hold:", round(result["buy_hold_return_pct"], 2), "%")
            print("Outperformance:", round(result["outperformance_pct"], 2), "%")
            print("-" * 45)

        except Exception as error:
            print("ERROR:", error)

    # ---------------- SAVE REPORTS ----------------

    if all_results:

        pd.DataFrame(all_results).to_csv(
            "backtest_v2_summary.csv",
            index=False
        )

        print("\nSaved: backtest_v2_summary.csv")

    if all_trades:

        pd.concat(
            all_trades,
            ignore_index=True
        ).to_csv(
            "backtest_v2_trades.csv",
            index=False
        )

        print("Saved: backtest_v2_trades.csv")

    if all_equity:

        pd.concat(
            all_equity,
            ignore_index=True
        ).to_csv(
            "backtest_v2_equity.csv",
            index=False
        )

        print("Saved: backtest_v2_equity.csv")

    print("\n" + "=" * 65)
    print("BACKTEST V2 FINISHED")
    print("REAL TRADING: DISABLED")
    print("=" * 65)


if __name__ == "__main__":
    main()