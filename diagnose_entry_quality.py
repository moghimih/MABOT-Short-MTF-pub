import pandas as pd

FILES = {
    "BASELINE": "risk_baseline_trades.csv",
    "ADX": "risk_adx_trades.csv",
    "BREAKOUT": "risk_breakout_trades.csv",
}

for name, file in FILES.items():

    df = pd.read_csv(file)

    df["initial_risk"] = (
        df["entry_price"] - df["initial_stop"]
    ) * df["quantity"]

    df["risk_multiple"] = (
        df["net_pnl"] / df["initial_risk"]
    )

    df["result"] = df["net_pnl"].apply(
        lambda x: "WIN" if x > 0 else "LOSS"
    )

    print("\n" + "=" * 65)
    print(name)
    print("=" * 65)

    print("\nRESULT BY HOLDING PERIOD:")

    df["holding_group"] = pd.cut(
        df["bars_held"],
        bins=[0, 2, 5, 10, 20, 10000],
        labels=["1-2", "3-5", "6-10", "11-20", "20+"]
    )

    result = df.groupby(
        "holding_group",
        observed=False
    ).agg(
        trades=("net_pnl", "size"),
        win_rate=("net_pnl", lambda x: (x > 0).mean() * 100),
        total_pnl=("net_pnl", "sum"),
        avg_pnl=("net_pnl", "mean"),
        avg_r=("risk_multiple", "mean"),
    )

    print(result.round(3).to_string())

    print("\nRESULT BY SYMBOL:")

    result = df.groupby("symbol").agg(
        trades=("net_pnl", "size"),
        win_rate=("net_pnl", lambda x: (x > 0).mean() * 100),
        total_pnl=("net_pnl", "sum"),
        avg_pnl=("net_pnl", "mean"),
        avg_bars=("bars_held", "mean"),
    )

    print(result.round(3).to_string())

print("\nDIAGNOSTIC COMPLETED")