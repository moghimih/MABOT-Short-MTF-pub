import pandas as pd

FILES = {
    "BASELINE": "risk_baseline_trades.csv",
    "ADX": "risk_adx_trades.csv",
    "BREAKOUT": "risk_breakout_trades.csv",
}

for name, file in FILES.items():

    df = pd.read_csv(file)

    df["stop_position"] = "AT_ENTRY"

    df.loc[
        df["final_stop"] > df["entry_price"],
        "stop_position"
    ] = "ABOVE_ENTRY"

    df.loc[
        df["final_stop"] < df["entry_price"],
        "stop_position"
    ] = "BELOW_ENTRY"

    print("\n" + "=" * 65)
    print(name)
    print("=" * 65)

    print("\nALL EXIT REASONS:")

    result = df.groupby("exit_reason").agg(
        trades=("net_pnl", "size"),
        winners=("net_pnl", lambda x: (x > 0).sum()),
        losers=("net_pnl", lambda x: (x < 0).sum()),
        total_pnl=("net_pnl", "sum"),
        avg_pnl=("net_pnl", "mean"),
    )

    print(result.round(3).to_string())

    print("\nSTOP LOSS BY FINAL STOP POSITION:")

    stops = df[df["exit_reason"] == "STOP_LOSS"]

    result = stops.groupby("stop_position").agg(
        trades=("net_pnl", "size"),
        winners=("net_pnl", lambda x: (x > 0).sum()),
        total_pnl=("net_pnl", "sum"),
        avg_pnl=("net_pnl", "mean"),
    )

    print(result.round(3).to_string())

print("\nDIAGNOSTIC COMPLETED")