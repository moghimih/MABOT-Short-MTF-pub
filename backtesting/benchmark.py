import pandas as pd

from config.settings import (
    SYMBOLS,
    INITIAL_CAPITAL,
    FEE_RATE,
    SLIPPAGE_RATE,
)
from data.loader import load_market_data


def run_buy_and_hold():
    print("=" * 65)
    print("MABOT - BUY AND HOLD BENCHMARK")
    print("=" * 65)

    markets = {
        symbol: load_market_data(symbol)
        for symbol in SYMBOLS
    }

    # Find common timestamps
    common_timestamps = set(markets[SYMBOLS[0]]["timestamp"])

    for symbol in SYMBOLS[1:]:
        common_timestamps &= set(markets[symbol]["timestamp"])

    common_timestamps = sorted(common_timestamps)

    if len(common_timestamps) < 2:
        raise ValueError("Not enough common timestamps.")

    start_time = common_timestamps[0]
    end_time = common_timestamps[-1]

    print(f"Common candles: {len(common_timestamps)}")
    print(f"Start: {start_time}")
    print(f"End:   {end_time}")

    # Align all markets
    aligned = {}

    for symbol, df in markets.items():
        part = df[df["timestamp"].isin(common_timestamps)].copy()
        part = part.sort_values("timestamp").reset_index(drop=True)

        if len(part) != len(common_timestamps):
            raise ValueError(f"Timestamp alignment failed: {symbol}")

        aligned[symbol] = part

    # Equal allocation
    allocation = INITIAL_CAPITAL / len(SYMBOLS)

    positions = {}

    for symbol, df in aligned.items():
        entry_open = float(df.iloc[0]["open"])

        if entry_open <= 0:
            raise ValueError(f"Invalid opening price: {symbol}")

        execution_price = entry_open * (1 + SLIPPAGE_RATE)

        total_cost = allocation
        quantity = total_cost / (
            execution_price * (1 + FEE_RATE)
        )

        positions[symbol] = {
            "quantity": quantity,
            "entry_cost": total_cost,
            "entry_price": execution_price,
        }

    # Calculate portfolio equity at every candle
    equity_rows = []

    for i, timestamp in enumerate(common_timestamps):
        equity = 0.0

        for symbol, df in aligned.items():
            close_price = float(df.iloc[i]["close"])

            if close_price <= 0:
                raise ValueError(f"Invalid close price: {symbol}")

            quantity = positions[symbol]["quantity"]

            # Hypothetical liquidation value after exit costs
            exit_price = close_price * (1 - SLIPPAGE_RATE)

            net_value = (
                quantity
                * exit_price
                * (1 - FEE_RATE)
            )

            equity += net_value

        equity_rows.append({
            "timestamp": timestamp,
            "equity": equity,
        })

    equity_df = pd.DataFrame(equity_rows)

    # Drawdown
    equity_df["peak"] = equity_df["equity"].cummax()

    equity_df["drawdown"] = (
        equity_df["equity"] / equity_df["peak"] - 1
    )

    final_equity = float(equity_df.iloc[-1]["equity"])

    total_return = (
        final_equity / INITIAL_CAPITAL - 1
    ) * 100

    max_drawdown = (
        equity_df["drawdown"].min() * 100
    )

    # Save results
    equity_df.to_csv(
        "buy_and_hold_equity.csv",
        index=False
    )

    summary = pd.DataFrame([{
        "strategy": "BUY_AND_HOLD",
        "initial_capital": INITIAL_CAPITAL,
        "final_equity": final_equity,
        "return_pct": total_return,
        "max_drawdown_pct": max_drawdown,
        "symbols": ",".join(SYMBOLS),
        "candles": len(common_timestamps),
    }])

    summary.to_csv(
        "buy_and_hold_summary.csv",
        index=False
    )

    print("\nBUY AND HOLD RESULTS")
    print("-" * 65)
    print(f"Initial capital: ${INITIAL_CAPITAL:.2f}")
    print(f"Final equity:    ${final_equity:.2f}")
    print(f"Total return:    {total_return:.2f}%")
    print(f"Max drawdown:    {max_drawdown:.2f}%")
    print("\nSaved:")
    print("buy_and_hold_equity.csv")
    print("buy_and_hold_summary.csv")


if __name__ == "__main__":
    run_buy_and_hold()