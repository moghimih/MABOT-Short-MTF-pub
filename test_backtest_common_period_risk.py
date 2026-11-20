import pandas as pd

from data.loader import load_all_markets
from indicators.engine import calculate_all_indicators

from strategies.baseline import BaselineStrategy
from strategies.adx_strategy import ADXStrategy
from strategies.breakout import BreakoutStrategy

from backtesting.engine import BacktestEngine
from backtesting.engine_with_risk import RiskBacktestEngine


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
            data["timestamp"], utc=True
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

    common_timestamps = set.intersection(
        *timestamp_sets.values()
    )

    common_timestamps = sorted(common_timestamps)

    if not common_timestamps:
        raise ValueError("No common timestamps found")

    print("COMMON TIMESTAMPS:", len(common_timestamps))

    for symbol, data in prepared.items():

        data = data[
            data["timestamp"].isin(common_timestamps)
        ].copy()

        data = data.sort_values(
            "timestamp"
        ).reset_index(drop=True)

        data["bars_in_segment"] = (
            data.groupby("segment_id").cumcount() + 1
        )

        prepared[symbol] = data

        print(
            f"{symbol}: {len(data)} rows | "
            f"{data['timestamp'].iloc[0]} | "
            f"{data['timestamp'].iloc[-1]}"
        )

    return prepared


def prepare_signals(markets, strategy):

    signals_by_symbol = {}

    for symbol, raw_data in markets.items():

        data = calculate_all_indicators(raw_data)

        signals = strategy.generate_signals(data).copy()

        if len(signals) != len(data):
            raise ValueError(
                f"{symbol}: strategy changed row count"
            )

        # Ensure the risk engine receives all required market columns.
        for column in [
            "timestamp", "open", "high", "low",
            "close", "ATR14", "segment_id",
        ]:
            if column not in signals.columns:
                signals[column] = data[column].to_numpy()

        signals_by_symbol[symbol] = signals

        print(
            f"{symbol}: "
            f"BUY={signals['BUY'].sum()} | "
            f"SELL={signals['SELL'].sum()}"
        )

    return signals_by_symbol


def main():

    print("=" * 75)
    print("MABOT - OLD ENGINE VS RISK ENGINE")
    print("=" * 75)

    markets = prepare_common_markets()

    strategies = {
        "BASELINE": BaselineStrategy(),
        "ADX": ADXStrategy(),
        "BREAKOUT": BreakoutStrategy(),
    }

    all_results = {}

    for strategy_name, strategy in strategies.items():

        print("\n" + "=" * 75)
        print("STRATEGY:", strategy_name)
        print("=" * 75)

        signals = prepare_signals(markets, strategy)

        # Old engine
        old_engine = BacktestEngine()

        old_result = old_engine.run(signals)
        old = old_result["summary"]

        # Risk-managed engine
        risk_engine = RiskBacktestEngine()

        risk_result = risk_engine.run(signals)
        risk = risk_result["summary"]

        all_results[strategy_name] = {
            "old_final_equity": old["final_equity"],
            "risk_final_equity": risk["final_equity"],

            "old_return_pct": old["total_return_pct"],
            "risk_return_pct": risk["total_return_pct"],

            "old_drawdown_pct": old["max_drawdown_pct"],
            "risk_drawdown_pct": risk["max_drawdown_pct"],

            "old_trades": old.get(
                "closed_trades", old.get("total_trades", 0)
            ),

            "risk_trades": risk["total_trades"],

            "old_win_rate_pct": old["win_rate_pct"],
            "risk_win_rate_pct": risk["win_rate_pct"],

            "old_profit_factor": old["profit_factor"],
            "risk_profit_factor": risk["profit_factor"],

            "risk_open_positions": risk["open_positions"],
            "risk_remaining_cash": risk["cash"],
        }

        print("\nOLD ENGINE:")
        for key, value in old.items():
            print(f"{key}: {value}")

        print("\nRISK ENGINE:")
        for key, value in risk.items():
            print(f"{key}: {value}")

        # Save individual trade logs.
        old_result["trades"].to_csv(
            f"old_{strategy_name.lower()}_trades.csv",
            index=False
        )

        risk_result["trades"].to_csv(
            f"risk_{strategy_name.lower()}_trades.csv",
            index=False
        )

    comparison = pd.DataFrame(all_results).T

    print("\n" + "=" * 100)
    print("FINAL COMPARISON")
    print("=" * 100)

    print(comparison.to_string())

    comparison.to_csv(
        "risk_engine_comparison.csv"
    )

    print("\nSaved:")
    print("risk_engine_comparison.csv")
    print("Individual trade logs saved.")


if __name__ == "__main__":
    main()