import pandas as pd

for strategy in ["baseline", "adx", "breakout"]:

    df = pd.read_csv(f"risk_{strategy}_trades.csv")

    df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True)
    df["exit_time"] = pd.to_datetime(df["exit_time"], utc=True)

    df = df.sort_values(["symbol", "entry_time"]).reset_index(drop=True)

    print("\n" + "=" * 70)
    print("STRATEGY:", strategy.upper())
    print("=" * 70)

    reentries = []

    for symbol, group in df.groupby("symbol"):

        group = group.sort_values("entry_time").reset_index(drop=True)

        for i in range(1, len(group)):

            previous = group.iloc[i - 1]
            current = group.iloc[i]

            gap_hours = (
                current["entry_time"] - previous["exit_time"]
            ).total_seconds() / 3600

            if 0 <= gap_hours <= 8:

                reentries.append({
                    "symbol": symbol,
                    "previous_exit": previous["exit_time"],
                    "previous_reason": previous["exit_reason"],
                    "previous_pnl": previous["net_pnl"],
                    "next_entry": current["entry_time"],
                    "next_pnl": current["net_pnl"],
                    "gap_hours": gap_hours,
                })

    result = pd.DataFrame(reentries)

    if result.empty:
        print("No reentries within 8 hours.")
    else:
        print("Reentries within 8 hours:", len(result))
        print("\nBy previous exit reason:")
        print(result.groupby("previous_reason").agg(
            count=("symbol", "count"),
            next_trade_avg_pnl=("next_pnl", "mean"),
            next_trade_total_pnl=("next_pnl", "sum"),
        ).round(4).to_string())

        print("\nFirst 20 examples:")
        print(result.head(20).to_string(index=False))