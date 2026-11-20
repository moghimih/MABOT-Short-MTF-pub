from data.loader import load_all_markets
from indicators.engine import calculate_all_indicators
from strategies.breakout import BreakoutStrategy


def main():

    print("=" * 60)
    print("MABOT - BREAKOUT STRATEGY MULTI-MARKET TEST")
    print("=" * 60)

    markets = load_all_markets()
    strategy = BreakoutStrategy()

    results = {}

    for symbol, raw_data in markets.items():

        data = calculate_all_indicators(raw_data)
        signals = strategy.generate_signals(data)

        results[symbol] = {
            "rows": len(signals),
            "buy": int(signals["BUY"].sum()),
            "sell": int(signals["SELL"].sum()),
            "buy_bool": signals["BUY"].dtype == bool,
            "sell_bool": signals["SELL"].dtype == bool,
        }

        print(f"\n{symbol}")
        print("-" * 40)
        print("Rows:", results[symbol]["rows"])
        print("BUY:", results[symbol]["buy"])
        print("SELL:", results[symbol]["sell"])
        print("BUY Boolean:", results[symbol]["buy_bool"])
        print("SELL Boolean:", results[symbol]["sell_bool"])

    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)

    for symbol, result in results.items():
        passed = result["buy_bool"] and result["sell_bool"]
        print(
            f"{symbol}: {'PASS' if passed else 'FAIL'} "
            f"| BUY={result['buy']} "
            f"| SELL={result['sell']}"
        )


if __name__ == "__main__":
    main()