from data.loader import load_all_markets
from indicators.engine import calculate_all_indicators

from strategies.baseline import BaselineStrategy
from strategies.adx_strategy import ADXStrategy
from strategies.breakout import BreakoutStrategy

from backtesting.engine import BacktestEngine


def main():

    print("=" * 70)
    print("MABOT - BACKTEST ENGINE TEST")
    print("=" * 70)

    markets = load_all_markets()

    strategies = {
        "BASELINE": BaselineStrategy(),
        "ADX": ADXStrategy(),
        "BREAKOUT": BreakoutStrategy(),
    }

    engine = BacktestEngine()

    for strategy_name, strategy in strategies.items():

        print("\n" + "=" * 70)
        print("STRATEGY:", strategy_name)
        print("=" * 70)

        signals_by_symbol = {}

        for symbol, raw_data in markets.items():

            data = calculate_all_indicators(raw_data)

            signals = strategy.generate_signals(data)

            signals_by_symbol[symbol] = signals

            print(
                f"{symbol}: "
                f"BUY={signals['BUY'].sum()} | "
                f"SELL={signals['SELL'].sum()}"
            )

        result = engine.run(signals_by_symbol)

        summary = result["summary"]

        print("\nBACKTEST SUMMARY")
        print("-" * 50)

        for key, value in summary.items():
            print(f"{key}: {value}")

        print("\nTRADES:", len(result["trades"]))
        print("EQUITY ROWS:", len(result["equity_curve"]))
        print("OPEN POSITIONS:", len(result["open_positions"]))


if __name__ == "__main__":
    main()
