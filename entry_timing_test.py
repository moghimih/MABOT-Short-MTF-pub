import pandas as pd
from pathlib import Path

from exit_policy_research import (
    FILES,
    INITIAL_CAPITAL,
    FEE,
    SLIPPAGE,
    load_data,
    calculate_indicators,
    backtest
)

print("=" * 70)
print("MABOT - ENTRY TIMING RESEARCH")
print("REAL TRADING: DISABLED")
print("=" * 70)


def buy_hold(df, start, end):

    test = df.iloc[start:end]

    entry = float(test.iloc[0]["open"]) * (1 + SLIPPAGE)
    exit_price = float(test.iloc[-1]["close"]) * (1 - SLIPPAGE)

    quantity = INITIAL_CAPITAL / (entry * (1 + FEE))

    final = quantity * exit_price * (1 - FEE)

    return (final / INITIAL_CAPITAL - 1) * 100


all_results = []

for symbol, filename in FILES.items():

    print(f"\nAnalyzing {symbol}...")

    if not Path(filename).exists():
        print("File not found:", filename)
        continue

    df = calculate_indicators(load_data(filename))

    df["EMA200"] = df["close"].ewm(
        span=200,
        adjust=False
    ).mean()

    baseline = df["BUY_SIGNAL"].copy()

    ema200_filter = (
        baseline
        & (df["close"] > df["EMA200"])
        & (df["EMA50"] > df["EMA200"])
    )

    # Fresh bullish crossover
    cross_up = (
        (df["EMA20"] > df["EMA50"])
        & (df["EMA20"].shift(1) <= df["EMA50"].shift(1))
        & (df["RSI"] > 50)
    )

    crossover = cross_up.fillna(False)

    crossover_ema200 = (
        crossover
        & (df["close"] > df["EMA200"])
        & (df["EMA50"] > df["EMA200"])
    )

    strategies = {
        "BASELINE_STATE": baseline,
        "EMA200_STATE": ema200_filter,
        "FRESH_CROSS": crossover,
        "CROSS_EMA200": crossover_ema200
    }

    split = int(len(df) * 0.70)

    periods = {
        "TRAINING": (50, split),
        "VALIDATION": (split, len(df))
    }

    for period, (start, end) in periods.items():

        benchmark = buy_hold(df, start, end)

        for strategy_name, signal in strategies.items():

            df["BUY_SIGNAL"] = signal.fillna(False)

            result = backtest(
                df,
                {"name": strategy_name},
                start,
                end
            )

            record = {
                "symbol": symbol,
                "period": period,
                "strategy": strategy_name,
                "return_pct": result["return_pct"],
                "trades": result["trades"],
                "win_rate": result["win_rate"],
                "profit_factor": result["profit_factor"],
                "max_drawdown": result["max_drawdown"],
                "buy_hold_return": benchmark
            }

            all_results.append(record)

            print(
                f"{period:12s} | "
                f"{strategy_name:18s} | "
                f"Return: {result['return_pct']:8.2f}% | "
                f"PF: {result['profit_factor']:6.3f} | "
                f"DD: {result['max_drawdown']:8.2f}% | "
                f"Trades: {result['trades']:3d}"
            )


if all_results:

    report = pd.DataFrame(all_results)

    report.to_csv(
        "entry_timing_results.csv",
        index=False
    )

    summary = report.groupby(
        ["period", "strategy"]
    ).agg(
        average_return=("return_pct", "mean"),
        median_return=("return_pct", "median"),
        positive_markets=(
            "return_pct",
            lambda x: int((x > 0).sum())
        ),
        average_drawdown=("max_drawdown", "mean"),
        average_profit_factor=("profit_factor", "mean"),
        total_trades=("trades", "sum"),
        average_buy_hold=("buy_hold_return", "mean")
    ).reset_index()

    summary.to_csv(
        "entry_timing_summary.csv",
        index=False
    )

    print("\n" + "=" * 70)
    print("ENTRY TIMING SUMMARY")
    print("=" * 70)

    print(summary.round(3).to_string(index=False))

    print("\nSaved: entry_timing_results.csv")
    print("Saved: entry_timing_summary.csv")


print("\nREAL TRADING: DISABLED")
print("RESEARCH FINISHED")