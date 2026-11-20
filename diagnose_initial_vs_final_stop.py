import pandas as pd

FILES = {
    "BASELINE": "risk_baseline_trades.csv",
    "ADX": "risk_adx_trades.csv",
    "BREAKOUT": "risk_breakout_trades.csv",
}

for name, file in FILES.items():

    df = pd.read_csv(file)

    df["initial_distance_pct"] = (
        df["initial_stop"] / df["entry_price"] - 1
    ) * 100

    df["final_distance_pct"] = (
        df["final_stop"] / df["entry_price"] - 1
    ) * 100

    df["stop_movement_pct"] = (
        df["final_stop"] / df["initial_stop"] - 1
    ) * 100

    df["result"] = df["net_pnl"].apply(
        lambda x: "WIN" if x > 0 else "LOSS"
    )

    print("\n" + "=" * 65)
    print(name)
    print("=" * 65)

    print("\nALL STOP_LOSS TRADES:")

    stops = df[df["exit_reason"] == "STOP_LOSS"]

    result = stops.groupby("result").agg(
        trades=("net_pnl", "size"),
        avg_initial_distance=("initial_distance_pct", "mean"),
        avg_final_distance=("final_distance_pct", "mean"),
        avg_stop_movement=("stop_movement_pct", "mean"),
        avg_bars=("bars_held", "mean"),
        total_pnl=("net_pnl", "sum"),
    )

    print(result.round(3).to_string())

    print("\nINITIAL STOP DISTANCE BY SYMBOL:")

    print(
        stops.groupby("symbol")["initial_distance_pct"]
        .agg(["count", "mean", "min", "max"])
        .round(3)
        .to_string()
    )

print("\nDIAGNOSTIC COMPLETED")