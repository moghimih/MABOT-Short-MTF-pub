import pandas as pd
from pathlib import Path

# ==============================================
# MABOT - EXIT POLICY RESEARCH V1
# SPOT / LONG ONLY
# REAL TRADING: DISABLED
# ==============================================

INITIAL_CAPITAL = 100.0
FEE = 0.002
SLIPPAGE = 0.0005

FILES = {
    "BTC": "btcusdt_history_extended.csv",
    "ETH": "ethusdt_history_extended.csv",
    "ZEC": "zecusdt_history_extended.csv",
    "XRP": "xrpusdt_history_extended.csv"
}

POLICIES = [
    {"name": "SIGNAL_ONLY"},
    {"name": "SL_2.5", "sl": 2.5},
    {"name": "SL_3.5", "sl": 3.5},
    {"name": "TP_2", "tp": 2.0},
    {"name": "SL_2.5_TP_2", "sl": 2.5, "tp": 2.0},
    {
        "name": "TRAIL_1.5",
        "sl": 3.0,
        "trail_activation": 2.0,
        "trail_gap": 1.5
    }
]


def load_data(filename):

    df = pd.read_csv(filename)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        unit="s",
        utc=True
    )

    df = df.sort_values("timestamp").reset_index(drop=True)

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="raise")

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
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14
    ).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))

    df["RSI"] = 100 - (100 / (1 + rs))

    df["RSI"] = df["RSI"].mask(
        (avg_loss == 0) & (avg_gain > 0), 100
    )

    df["RSI"] = df["RSI"].mask(
        (avg_loss == 0) & (avg_gain == 0), 50
    )

    df["BUY_SIGNAL"] = (
        (df["EMA20"] > df["EMA50"]) &
        (df["RSI"] > 50)
    ).fillna(False)

    df["SELL_SIGNAL"] = (
        (df["EMA20"] < df["EMA50"]) |
        (df["RSI"] < 45)
    ).fillna(False)

    return df


def backtest(df, policy, start, end):

    cash = INITIAL_CAPITAL
    quantity = 0.0

    position = False

    entry_price = 0.0
    invested = 0.0
    entry_time = None

    highest_high = 0.0

    trades = []
    equity = [INITIAL_CAPITAL]

    for i in range(start, end):

        row = df.iloc[i]
        previous = df.iloc[i - 1]

        op = float(row["open"])
        hi = float(row["high"])
        lo = float(row["low"])
        close = float(row["close"])

        buy_signal = bool(previous["BUY_SIGNAL"])
        sell_signal = bool(previous["SELL_SIGNAL"])

        entered_now = False

        # ---------------- BUY ----------------

        if not position and buy_signal:

            entry_price = op * (1 + SLIPPAGE)
            invested = cash

            quantity = cash / (
                entry_price * (1 + FEE)
            )

            cash = 0.0
            entry_time = row["timestamp"]

            highest_high = entry_price
            position = True
            entered_now = True

        # ---------------- POSITION MANAGEMENT ----------------

        if position:

            stop_price = None
            target_price = None

            if "sl" in policy:
                stop_price = entry_price * (
                    1 - policy["sl"] / 100
                )

            if "tp" in policy:
                target_price = entry_price * (
                    1 + policy["tp"] / 100
                )

            # Trailing stop based on previously observed highs.
            if "trail_activation" in policy:

                activation_price = entry_price * (
                    1 + policy["trail_activation"] / 100
                )

                if highest_high >= activation_price:

                    trail_price = highest_high * (
                        1 - policy["trail_gap"] / 100
                    )

                    if stop_price is None:
                        stop_price = trail_price
                    else:
                        stop_price = max(
                            stop_price,
                            trail_price
                        )

            exit_raw = None
            reason = None

            # Gap through stop or target.
            if stop_price is not None and op <= stop_price:

                exit_raw = op
                reason = "STOP_GAP"

            elif target_price is not None and op >= target_price:

                exit_raw = op
                reason = "TARGET_GAP"

            # Previously known sell signal.
            elif sell_signal and not entered_now:

                exit_raw = op
                reason = "SELL_SIGNAL"

            else:

                hit_stop = (
                    stop_price is not None
                    and lo <= stop_price
                )

                hit_target = (
                    target_price is not None
                    and hi >= target_price
                )

                # Conservative assumption:
                # If both levels are touched, stop goes first.
                if hit_stop:

                    exit_raw = stop_price
                    reason = "STOP"

                elif hit_target:

                    exit_raw = target_price
                    reason = "TAKE_PROFIT"

            # ---------------- SELL ----------------

            if exit_raw is not None:

                execution_price = exit_raw * (
                    1 - SLIPPAGE
                )

                cash = (
                    quantity *
                    execution_price *
                    (1 - FEE)
                )

                pnl = cash - invested

                trades.append({
                    "entry_time": entry_time,
                    "exit_time": row["timestamp"],
                    "entry_price": entry_price,
                    "exit_price": execution_price,
                    "net_pnl": pnl,
                    "return_pct": pnl / invested * 100,
                    "exit_reason": reason
                })

                quantity = 0.0
                position = False

                entry_price = 0.0
                highest_high = 0.0

                entry_time = None

            else:

                # Trailing stop updates only after this candle.
                highest_high = max(highest_high, hi)

        # ---------------- EQUITY ----------------

        if position:

            current_equity = (
                quantity *
                close *
                (1 - SLIPPAGE) *
                (1 - FEE)
            )

        else:

            current_equity = cash

        equity.append(current_equity)

    # ---------------- FINAL EXIT ----------------

    if position:

        last = df.iloc[end - 1]

        execution_price = float(last["close"]) * (
            1 - SLIPPAGE
        )

        cash = (
            quantity *
            execution_price *
            (1 - FEE)
        )

        pnl = cash - invested

        trades.append({
            "entry_time": entry_time,
            "exit_time": last["timestamp"],
            "entry_price": entry_price,
            "exit_price": execution_price,
            "net_pnl": pnl,
            "return_pct": pnl / invested * 100,
            "exit_reason": "END_OF_TEST"
        })

        equity[-1] = cash

    # ---------------- METRICS ----------------

    trade_df = pd.DataFrame(trades)

    series = pd.Series(equity)

    drawdown = (
        (series - series.cummax()) /
        series.cummax()
    ) * 100

    if not trade_df.empty:

        wins = trade_df[trade_df["net_pnl"] > 0]
        losses = trade_df[trade_df["net_pnl"] < 0]

        gross_profit = wins["net_pnl"].sum()
        gross_loss = abs(losses["net_pnl"].sum())

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else float("inf") if gross_profit > 0
            else 0
        )

        win_rate = len(wins) / len(trade_df) * 100

    else:

        profit_factor = 0
        win_rate = 0

    return {
        "final_capital": cash,
        "return_pct": (cash / INITIAL_CAPITAL - 1) * 100,
        "trades": len(trade_df),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown": drawdown.min(),
        "trade_details": trade_df
    }


def main():

    print("=" * 65)
    print("MABOT - EXIT POLICY RESEARCH V1")
    print("REAL TRADING: DISABLED")
    print("=" * 65)

    all_results = []
    all_trades = []

    for symbol, filename in FILES.items():

        print(f"\nLoading {symbol}...")

        if not Path(filename).exists():
            print("File not found:", filename)
            continue

        df = calculate_indicators(load_data(filename))

        # First 70% only: research period.
        split = int(len(df) * 0.70)

        for policy in POLICIES:

            result = backtest(
                df,
                policy,
                start=50,
                end=split
            )

            record = {
                "symbol": symbol,
                "policy": policy["name"],
                "return_pct": result["return_pct"],
                "final_capital": result["final_capital"],
                "trades": result["trades"],
                "win_rate": result["win_rate"],
                "profit_factor": result["profit_factor"],
                "max_drawdown": result["max_drawdown"]
            }

            all_results.append(record)

            if not result["trade_details"].empty:

                details = result["trade_details"].copy()

                details["symbol"] = symbol
                details["policy"] = policy["name"]

                all_trades.append(details)

            print(
                f"{policy['name']:20s}",
                f"Return: {result['return_pct']:8.2f}%",
                f"PF: {result['profit_factor']:6.3f}",
                f"DD: {result['max_drawdown']:8.2f}%"
            )

    if all_results:

        report = pd.DataFrame(all_results)

        report.to_csv(
            "exit_policy_training.csv",
            index=False
        )

        aggregate = report.groupby("policy").agg(
            avg_return=("return_pct", "mean"),
            avg_drawdown=("max_drawdown", "mean"),
            avg_profit_factor=("profit_factor", "mean"),
            total_trades=("trades", "sum")
        ).reset_index()

        aggregate.to_csv(
            "exit_policy_training_summary.csv",
            index=False
        )

        print("\n" + "=" * 65)
        print("AGGREGATE TRAINING RESULTS")
        print("=" * 65)

        print(
            aggregate.round(3).to_string(index=False)
        )

        print("\nSaved: exit_policy_training.csv")
        print("Saved: exit_policy_training_summary.csv")

    if all_trades:

        pd.concat(
            all_trades,
            ignore_index=True
        ).to_csv(
            "exit_policy_training_trades.csv",
            index=False
        )

        print("Saved: exit_policy_training_trades.csv")

    print("\nREAL TRADING: DISABLED")
    print("RESEARCH FINISHED")


if __name__ == "__main__":
    main()