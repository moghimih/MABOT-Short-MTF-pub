import pandas as pd

from adx_4h_research import (
    FILES,
    load_data,
    add_indicators,
)

from indicators.engine import calculate_all_indicators
from strategies.baseline import BaselineStrategy


SYMBOL_MAP = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "ZEC": "ZECUSDT",
    "XRP": "XRPUSDT",
}


def compare_symbol(symbol, filename):
    print("\n" + "=" * 65)
    print(f"COMPARING {symbol}")
    print("=" * 65)

    # Original research engine
    old_data = add_indicators(load_data(filename))

    # New modular engine
    market_symbol = SYMBOL_MAP[symbol]
    new_data = calculate_all_indicators(
        __import__(
            "data.loader",
            fromlist=["load_market_data"]
        ).load_market_data(market_symbol)
    )

    # Generate modular strategy signals
    new_signals = BaselineStrategy().generate_signals(new_data)

    # Align by timestamp
    old = old_data.set_index("timestamp")
    new = new_signals.set_index("timestamp")

    common = old.index.intersection(new.index)

    old = old.loc[common]
    new = new.loc[common]

    # Compare exact signals
    buy_diff = old["BUY_BASELINE"].astype(bool) != new["BUY"]
    sell_diff = old["SELL_SIGNAL"].astype(bool) != new["SELL"]

    buy_errors = int(buy_diff.sum())
    sell_errors = int(sell_diff.sum())

    print(f"Old rows: {len(old_data)}")
    print(f"New rows: {len(new_data)}")
    print(f"Matched timestamps: {len(common)}")

    print(f"Old BUY signals: {old['BUY_BASELINE'].sum()}")
    print(f"New BUY signals: {new['BUY'].sum()}")
    print(f"BUY differences: {buy_errors}")

    print(f"Old SELL signals: {old['SELL_SIGNAL'].sum()}")
    print(f"New SELL signals: {new['SELL'].sum()}")
    print(f"SELL differences: {sell_errors}")

    if buy_errors:
        print("\nFirst BUY differences:")
        print(
            pd.DataFrame({
                "old": old.loc[buy_diff, "BUY_BASELINE"],
                "new": new.loc[buy_diff, "BUY"],
            }).head(5).to_string()
        )

    if sell_errors:
        print("\nFirst SELL differences:")
        print(
            pd.DataFrame({
                "old": old.loc[sell_diff, "SELL_SIGNAL"],
                "new": new.loc[sell_diff, "SELL"],
            }).head(5).to_string()
        )

    passed = (
        len(common) == len(old_data) == len(new_data)
        and buy_errors == 0
        and sell_errors == 0
    )

    print("\nRESULT:", "PASS" if passed else "FAIL")

    return passed


def main():
    print("=" * 65)
    print("MABOT - OLD VS MODULAR STRATEGY SIGNAL COMPARISON")
    print("=" * 65)

    results = {}

    for symbol, filename in FILES.items():
        results[symbol] = compare_symbol(symbol, filename)

    print("\n" + "=" * 65)
    print("FINAL SUMMARY")
    print("=" * 65)

    for symbol, passed in results.items():
        print(f"{symbol}: {'PASS' if passed else 'FAIL'}")

    all_passed = all(results.values())

    print("\nOVERALL:", "PASSED" if all_passed else "FAILED")


if __name__ == "__main__":
    main()