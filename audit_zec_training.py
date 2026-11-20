import pandas as pd

DATA_FILE = "zecusdt_history_extended.csv"
TRADE_FILE = "exit_policy_training_trades.csv"

df = pd.read_csv(DATA_FILE)
trades = pd.read_csv(TRADE_FILE)

df["timestamp"] = pd.to_datetime(
    df["timestamp"],
    unit="s",
    utc=True
)

split = int(len(df) * 0.70)

print("=" * 60)
print("MABOT - ZEC TRAINING AUDIT")
print("=" * 60)

print("Total candles:", len(df))
print("Training candles:", split)
print("Validation starts:", df.iloc[split]["timestamp"])

zec = trades[
    (trades["symbol"] == "ZEC") &
    (trades["policy"] == "SIGNAL_ONLY")
].copy()

zec["entry_time"] = pd.to_datetime(
    zec["entry_time"],
    utc=True
)

zec["exit_time"] = pd.to_datetime(
    zec["exit_time"],
    utc=True
)

zec["net_pnl"] = pd.to_numeric(zec["net_pnl"])

print("\nTraining trades:", len(zec))

print("\nTOP 10 PROFITABLE TRADES")
print("-" * 60)

print(
    zec.nlargest(10, "net_pnl")[
        ["entry_time", "exit_time", "net_pnl", "return_pct"]
    ].to_string(index=False)
)

gross_profit = zec.loc[
    zec["net_pnl"] > 0, "net_pnl"
].sum()

gross_loss = abs(
    zec.loc[zec["net_pnl"] < 0, "net_pnl"].sum()
)

print("\nTotal winning profit:", round(gross_profit, 3))
print("Total losing amount:", round(gross_loss, 3))

if gross_profit > 0:
    best_trade = zec["net_pnl"].max()

    print(
        "Largest winner share of gross profit:",
        round(best_trade / gross_profit * 100, 2),
        "%"
    )

print("\n" + "=" * 60)
print("AUDIT FINISHED")
print("=" * 60)