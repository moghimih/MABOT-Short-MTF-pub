import pandas as pd

FILES = {
    "BASELINE": "risk_baseline_trades.csv",
    "ADX": "risk_adx_trades.csv",
    "BREAKOUT": "risk_breakout_trades.csv",
}

for name, file in FILES.items():

    df = pd.read_csv(file)

    df["stop_distance_pct"] = (
        (df["final_stop"] / df["entry_price"]) - 1
    ) * 100

    df["result_group"] = df["net_pnl"].apply(
        lambda x: "WIN" if x > 0 else "LOSS"
    )

    print("\n" + "=" * 65)
    print(name)
    print("=" * 65)

    stops = df[df["exit_reason"] == "STOP_LOSS"]

    print("\nSTOP DISTANCE BY RESULT:")

    result = stops.groupby("result_group").agg(
        trades=("net_pnl", "size"),
        avg_stop_distance=("stop_distance_pct", "mean"),
        min_stop_distance=("stop_distance_pct", "min"),
        max_stop_distance=("stop_distance_pct", "max"),
        avg_bars=("bars_held", "mean"),
        total_pnl=("net_pnl", "sum"),
    )

    print(result.round(3).to_string())

    print("\nLOSING STOP TRADES - FIRST 10:")

    cols = [
        "symbol",
        "entry_price",
        "final_stop",
        "stop_distance_pct",
        "bars_held",
        "net_pnl",
    ]

    print(
        stops[stops["net_pnl"] < 0]
        [cols]
        .sort_values("net_pnl")
        .head(10)
        .round(4)
        .to_string(index=False)
    )

print("\nDIAGNOSTIC COMPLETED")