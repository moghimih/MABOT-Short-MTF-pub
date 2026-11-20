import pandas as pd

STRATEGIES = [
    "baseline",
    "adx",
    "breakout",
]

for strategy in STRATEGIES:

    filename = f"risk_{strategy}_trades.csv"

    df = pd.read_csv(filename)

    print("\n" + "=" * 75)
    print("STRATEGY:", strategy.upper())
    print("=" * 75)

    print("\nEXIT REASONS:")

    print(
        df.groupby("exit_reason").agg(
            trades=("net_pnl", "count"),
            total_pnl=("net_pnl", "sum"),
            avg_pnl=("net_pnl", "mean"),
            win_rate=("net_pnl", lambda x: (x > 0).mean() * 100),
        ).round(3).to_string()
    )

    print("\nRESULT BY SYMBOL:")

    print(
        df.groupby("symbol").agg(
            trades=("net_pnl", "count"),
            total_pnl=("net_pnl", "sum"),
            avg_pnl=("net_pnl", "mean"),
            win_rate=("net_pnl", lambda x: (x > 0).mean() * 100),
            avg_bars=("bars_held", "mean"),
        ).round(3).to_string()
    )

    print("\nOVERALL:")

    print("Trades:", len(df))
    print("Average profit:", round(df["net_pnl"].mean(), 4))
    print("Average winner:", round(
        df.loc[df.net_pnl > 0, "net_pnl"].mean(), 4
    ))
    print("Average loser:", round(
        df.loc[df.net_pnl < 0, "net_pnl"].mean(), 4
    ))
    print("Average holding bars:", round(df["bars_held"].mean(), 2))