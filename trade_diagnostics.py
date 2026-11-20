import pandas as pd

FILE = "backtest_v2_trades.csv"

df = pd.read_csv(FILE)

if df.empty:
    print("No trades found.")
    raise SystemExit

df["net_pnl"] = pd.to_numeric(df["net_pnl"])
df["net_return_pct"] = pd.to_numeric(df["net_return_pct"])
df["holding_hours"] = pd.to_numeric(df["holding_hours"])

df["exit_time"] = pd.to_datetime(
    df["exit_time"], utc=True
)

print("=" * 65)
print("MABOT - TRADE DIAGNOSTICS")
print("=" * 65)

for symbol, group in df.groupby("symbol"):

    group = group.sort_values("exit_time")

    winners = group[group["net_pnl"] > 0]
    losers = group[group["net_pnl"] < 0]

    gross_profit = winners["net_pnl"].sum()
    gross_loss = abs(losers["net_pnl"].sum())

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0 else float("inf")
    )

    # Maximum consecutive losing trades
    current_streak = 0
    max_streak = 0

    for pnl in group["net_pnl"]:
        if pnl < 0:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    print(f"\nMARKET: {symbol}")
    print("-" * 50)

    print("Total trades:", len(group))
    print("Winning trades:", len(winners))
    print("Losing trades:", len(losers))

    print("Average win:",
          round(winners["net_return_pct"].mean(), 2), "%")

    print("Average loss:",
          round(losers["net_return_pct"].mean(), 2), "%")

    print("Best trade:",
          round(group["net_return_pct"].max(), 2), "%")

    print("Worst trade:",
          round(group["net_return_pct"].min(), 2), "%")

    print("Average holding hours:",
          round(group["holding_hours"].mean(), 1))

    print("Profit factor:",
          round(profit_factor, 3))

    print("Maximum consecutive losses:", max_streak)

    print("\nTHREE BEST TRADES:")

    for _, trade in group.nlargest(
        3, "net_pnl"
    ).iterrows():

        print(
            trade["exit_time"],
            "| Return:", round(trade["net_return_pct"], 2), "%",
            "| PnL:", round(trade["net_pnl"], 3)
        )

    print("\nTHREE WORST TRADES:")

    for _, trade in group.nsmallest(
        3, "net_pnl"
    ).iterrows():

        print(
            trade["exit_time"],
            "| Return:", round(trade["net_return_pct"], 2), "%",
            "| PnL:", round(trade["net_pnl"], 3)
        )

print("\n" + "=" * 65)
print("DIAGNOSTICS FINISHED")
print("=" * 65)