import pandas as pd
from pathlib import Path

from exit_policy_research import (
    FILES,
    POLICIES,
    load_data,
    calculate_indicators,
    backtest
)

INITIAL_CAPITAL = 100.0
FEE = 0.002
SLIPPAGE = 0.0005

all_results = []
all_trades = []

print("=" * 65)
print("MABOT - EXIT POLICY VALIDATION")
print("REAL TRADING: DISABLED")
print("=" * 65)

for symbol, filename in FILES.items():

    print(f"\nValidating {symbol}...")

    if not Path(filename).exists():
        print("File not found:", filename)
        continue

    df = calculate_indicators(
        load_data(filename)
    )

    split = int(len(df) * 0.70)

    test = df.iloc[split:].reset_index(drop=True)

    # Buy & Hold benchmark
    start_price = float(test.iloc[0]["open"])
    end_price = float(test.iloc[-1]["close"])

    buy_price = start_price * (1 + SLIPPAGE)

    quantity = INITIAL_CAPITAL / (
        buy_price * (1 + FEE)
    )

    sell_price = end_price * (1 - SLIPPAGE)

    buy_hold_final = (
        quantity * sell_price * (1 - FEE)
    )

    buy_hold_return = (
        buy_hold_final / INITIAL_CAPITAL - 1
    ) * 100

    for policy in POLICIES:

        result = backtest(
            df,
            policy,
            start=split,
            end=len(df)
        )

        record = {
            "symbol": symbol,
            "policy": policy["name"],
            "initial_capital": INITIAL_CAPITAL,
            "final_capital": result["final_capital"],
            "return_pct": result["return_pct"],
            "trades": result["trades"],
            "win_rate": result["win_rate"],
            "profit_factor": result["profit_factor"],
            "max_drawdown": result["max_drawdown"],
            "buy_hold_return": buy_hold_return
        }

        all_results.append(record)

        details = result["trade_details"].copy()

        if not details.empty:
            details["symbol"] = symbol
            details["policy"] = policy["name"]
            all_trades.append(details)

        print(
            f"{policy['name']:20s} "
            f"Return: {result['return_pct']:8.2f}% "
            f"PF: {result['profit_factor']:6.3f} "
            f"DD: {result['max_drawdown']:8.2f}% "
            f"Trades: {result['trades']:3d}"
        )

# Save individual results
if all_results:

    report = pd.DataFrame(all_results)

    report.to_csv(
        "exit_policy_validation.csv",
        index=False
    )

    # Equal-weight average across the four markets
    summary = report.groupby("policy").agg(
        average_return=("return_pct", "mean"),
        median_return=("return_pct", "median"),
        positive_markets=(
            "return_pct",
            lambda x: int((x > 0).sum())
        ),
        average_drawdown=("max_drawdown", "mean"),
        average_buy_hold=("buy_hold_return", "mean"),
        total_trades=("trades", "sum")
    ).reset_index()

    # Calculate pooled profit factor from all trades
    if all_trades:

        combined = pd.concat(
            all_trades,
            ignore_index=True
        )

        pooled_pf = {}

        for policy_name, group in combined.groupby("policy"):

            profits = group.loc[
                group["net_pnl"] > 0,
                "net_pnl"
            ].sum()

            losses = abs(
                group.loc[
                    group["net_pnl"] < 0,
                    "net_pnl"
                ].sum()
            )

            if losses > 0:
                pf = profits / losses
            elif profits > 0:
                pf = float("inf")
            else:
                pf = 0.0

            pooled_pf[policy_name] = pf

        summary["pooled_profit_factor"] = (
            summary["policy"].map(pooled_pf)
        )

        combined.to_csv(
            "exit_policy_validation_trades.csv",
            index=False
        )

    summary.to_csv(
        "exit_policy_validation_summary.csv",
        index=False
    )

    print("\n" + "=" * 65)
    print("VALIDATION SUMMARY")
    print("=" * 65)

    print(summary.round(3).to_string(index=False))

    print("\nSaved: exit_policy_validation.csv")
    print("Saved: exit_policy_validation_summary.csv")

    if all_trades:
        print("Saved: exit_policy_validation_trades.csv")

print("\n" + "=" * 65)
print("VALIDATION FINISHED")
print("REAL TRADING: DISABLED")
print("=" * 65)