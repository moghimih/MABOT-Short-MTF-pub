import pandas as pd

FILES = {
    "BTC": "btcusdt_history_extended.csv",
    "ETH": "ethusdt_history_extended.csv",
    "ZEC": "zecusdt_history_extended.csv",
    "XRP": "xrpusdt_history_extended.csv"
}

INITIAL_CAPITAL = 100
FEE = 0.002
SLIPPAGE = 0.0005
TEST_RATIO = 0.30

print("=" * 60)
print("MABOT - BUY & HOLD BENCHMARK")
print("=" * 60)

for symbol, filename in FILES.items():

    df = pd.read_csv(filename)

    split = int(len(df) * (1 - TEST_RATIO))
    test = df.iloc[split:].reset_index(drop=True)

    start_price = float(test.iloc[0]["open"])
    end_price = float(test.iloc[-1]["close"])

    buy_price = start_price * (1 + SLIPPAGE)
    sell_price = end_price * (1 - SLIPPAGE)

    quantity = INITIAL_CAPITAL / (
        buy_price * (1 + FEE)
    )

    final_capital = (
        quantity * sell_price * (1 - FEE)
    )

    returns = (
        final_capital / INITIAL_CAPITAL - 1
    ) * 100

    print(f"\n{symbol}")
    print("-" * 35)
    print("Start price:", start_price)
    print("End price:", end_price)
    print("Initial capital:", INITIAL_CAPITAL)
    print("Final capital:", round(final_capital, 2))
    print("Buy & Hold return:", round(returns, 2), "%")

print("\n" + "=" * 60)
print("BENCHMARK FINISHED")
print("=" * 60)