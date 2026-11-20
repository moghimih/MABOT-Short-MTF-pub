import pandas as pd
from pathlib import Path

# =========================================
# MABOT - TRADE EXCURSION ANALYSIS
# MFE / MAE
# REAL TRADING: DISABLED
# =========================================

FEE_RATE = 0.002
SLIPPAGE_RATE = 0.0005

FILES = {
    "BTC": "btcusdt_history_extended.csv",
    "ETH": "ethusdt_history_extended.csv",
    "ZEC": "zecusdt_history_extended.csv",
    "XRP": "xrpusdt_history_extended.csv"
}

trades = pd.read_csv("backtest_v2_trades.csv")

if trades.empty:
    raise ValueError("No trades found.")

results = []

print("=" * 65)
print("MABOT - TRADE EXCURSION ANALYSIS")
print("=" * 65)

for symbol, filename in FILES.items():

    print(f"\nAnalyzing {symbol}...")

    if not Path(filename).exists():
        print("Market data file not found.")
        continue

    df = pd.read_csv(filename)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        unit="s",
        utc=True
    )

    market_trades = trades[
        trades["symbol"] == symbol
    ].copy()

    for _, trade in market_trades.iterrows():

        entry_time = pd.to_datetime(
            trade["entry_time"],
            utc=True
        )

        exit_time = pd.to_datetime(
            trade["exit_time"],
            utc=True
        )

        # در خروج با سیگنال، کندل خروج را حذف می‌کنیم
        if trade["exit_reason"] == "END_OF_TEST":

            window = df[
                (df["timestamp"] >= entry_time) &
                (df["timestamp"] <= exit_time)
            ]

        else:

            window = df[
                (df["timestamp"] >= entry_time) &
                (df["timestamp"] < exit_time)
            ]

        if window.empty:
            print("WARNING: Empty candle window:", symbol)
            continue

        highest_price = float(window["high"].max())
        lowest_price = float(window["low"].min())

        quantity = float(trade["quantity"])
        invested = float(trade["invested_capital"])

        # بهترین خروج فرضی با احتساب هزینه‌ها
        best_exit_value = (
            quantity *
            highest_price *
            (1 - SLIPPAGE_RATE) *
            (1 - FEE_RATE)
        )

        # بدترین خروج فرضی با احتساب هزینه‌ها
        worst_exit_value = (
            quantity *
            lowest_price *
            (1 - SLIPPAGE_RATE) *
            (1 - FEE_RATE)
        )

        mfe = (
            best_exit_value / invested - 1
        ) * 100

        mae = (
            worst_exit_value / invested - 1
        ) * 100

        results.append({
            "symbol": symbol,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "realized_return_pct": float(
                trade["net_return_pct"]
            ),
            "MFE_net_pct": mfe,
            "MAE_net_pct": mae,
            "holding_hours": float(
                trade["holding_hours"]
            ),
            "exit_reason": trade["exit_reason"]
        })


result_df = pd.DataFrame(results)

if result_df.empty:
    raise ValueError("No excursion results generated.")

result_df.to_csv(
    "backtest_v2_excursions.csv",
    index=False
)

for symbol in FILES:

    group = result_df[
        result_df["symbol"] == symbol
    ]

    if group.empty:
        continue

    losers = group[
        group["realized_return_pct"] < 0
    ]

    winners = group[
        group["realized_return_pct"] > 0
    ]

    losing_but_profitable = losers[
        losers["MFE_net_pct"] > 0
    ]

    never_profitable = losers[
        losers["MFE_net_pct"] <= 0
    ]

    print("\n" + "=" * 55)
    print("MARKET:", symbol)
    print("=" * 55)

    print("Total trades:", len(group))

    print(
        "Average MFE:",
        round(group["MFE_net_pct"].mean(), 2), "%"
    )

    print(
        "Average MAE:",
        round(group["MAE_net_pct"].mean(), 2), "%"
    )

    print(
        "Losing trades:",
        len(losers)
    )

    print(
        "Losing trades that were temporarily profitable:",
        len(losing_but_profitable)
    )

    print(
        "Losing trades never profitable:",
        len(never_profitable)
    )

    if not losers.empty:

        print(
            "Average MFE of losing trades:",
            round(losers["MFE_net_pct"].mean(), 2), "%"
        )

    if not winners.empty:

        print(
            "Average MFE of winning trades:",
            round(winners["MFE_net_pct"].mean(), 2), "%"
        )

    print("\nWorst trades that had a profitable opportunity:")

    for _, row in losing_but_profitable.nsmallest(
        3, "realized_return_pct"
    ).iterrows():

        print(
            "Realized:",
            round(row["realized_return_pct"], 2), "%",
            "| MFE:",
            round(row["MFE_net_pct"], 2), "%",
            "| MAE:",
            round(row["MAE_net_pct"], 2), "%"
        )

print("\n" + "=" * 65)
print("ANALYSIS FINISHED")
print("Saved: backtest_v2_excursions.csv")
print("=" * 65)