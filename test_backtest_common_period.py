import pandas as pd

from data.loader import load_all_markets
from indicators.engine import calculate_all_indicators

from strategies.baseline import BaselineStrategy
from strategies.adx_strategy import ADXStrategy
from strategies.breakout import BreakoutStrategy

from backtesting.engine import BacktestEngine


START_DATE = "2025-07-07 16:30:00+00:00"
END_DATE = "2026-11-16 12:30:00+00:00"


def prepare_common_markets():

    markets = load_all_markets()

    start = pd.Timestamp(START_DATE)
    end = pd.Timestamp(END_DATE)

    prepared = {}
    timestamp_sets = {}

    print("\nPREPARING COMMON PERIOD")

    for symbol, raw_data in markets.items():

        data = raw_data.copy()

        data["timestamp"] = pd.to_datetime(
            data["timestamp"],
            utc=True
        )

        data = data[
            (data["timestamp"] >= start)
            & (data["timestamp"] <= end)
        ].copy()

        data = data.sort_values(
            "timestamp"
        ).reset_index(drop=True)

        timestamp_sets[symbol] = set(data["timestamp"])

        prepared[symbol] = data

    # Find timestamps shared by all four markets
    common_timestamps = set.intersection(
        *timestamp_sets.values()
    )

    common_timestamps = sorted(common_timestamps)

    if not common_timestamps:
        raise ValueError("No common timestamps found")

    print("\nCOMMON TIMESTAMP COUNT:", len(common_timestamps))

    for symbol, data in prepared.items():

        data = data[
            data["timestamp"].isin(common_timestamps)
        ].copy()

        data = data.sort_values(
            "timestamp"
        ).reset_index(drop=True)

        # Reset warmup counter inside each segment
        data["bars_in_segment"] = (
            data.groupby("segment_id").cumcount() + 1
        )

        prepared[symbol] = data

        print(
            f"{symbol}: {len(data)} rows | "
            f"First: {data['timestamp'].iloc[0]} | "
            f"Last: {data['timestamp'].iloc[-1]}"
        )

    return prepared


def main():

    print("=" * 70)
    print("MABOT - COMMON PERIOD BACKTEST")
    print("=" * 70)

    markets = prepare_common_markets()

    strategies = {
        "BASELINE": BaselineStrategy(),
        "ADX": ADXStrategy(),
        "BREAKOUT": BreakoutStrategy(),
    }

    engine = BacktestEngine()

    all_results = {}

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

        all_results[strategy_name] = result["summary"]

        print("\nBACKTEST SUMMARY")

        for key, value in result["summary"].items():
            print(f"{key}: {value}")

    print("\n" + "=" * 70)
    print("FINAL STRATEGY COMPARISON")
    print("=" * 70)

    comparison = pd.DataFrame(all_results).T

    columns = [
        "final_equity",
        "total_return_pct",
        "max_drawdown_pct",
        "closed_trades",
        "win_rate_pct",
        "profit_factor",
    ]

    print(comparison[columns].to_string())

    comparison.to_csv(
        "common_period_strategy_comparison.csv",
        index=True
    )

    print("\nSaved: common_period_strategy_comparison.csv")


if __name__ == "__main__":
    main()