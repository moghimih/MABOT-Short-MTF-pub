"""MABOT - Ichimoku component isolation test.

Separates the contribution of Ichimoku entry rules from Ichimoku exit rules.
Uses the same native 4h gap-aware data, train/validation split, costs and
next-open execution convention as the preceding research scripts.
READ ONLY: does not modify source CSVs and places no real orders.
"""

from pathlib import Path
import math
import numpy as np
import pandas as pd

from ichimoku_4h_research import (
    FILES,
    INITIAL_CAPITAL,
    FEE_RATE,
    SLIPPAGE_RATE,
    TRAIN_RATIO,
    WARMUP_BARS,
    load_data,
    add_indicators,
    add_ichimoku_by_segment,
    backtest,
    buy_hold_return,
)


STRATEGIES = [
    ("BASELINE", "BUY_BASELINE", "SELL_SIGNAL"),
    ("ADX20_PLUS_DI", "BUY_ADX", "SELL_SIGNAL"),
    ("ICHIMOKU_ENTRY_BASE_EXIT", "BUY_ICHIMOKU", "SELL_SIGNAL"),
    ("BASE_ENTRY_ICHIMOKU_EXIT", "BUY_BASELINE", "SELL_ICHIMOKU"),
    ("ICHIMOKU_FULL", "BUY_ICHIMOKU", "SELL_ICHIMOKU"),
]


def load_common_data():
    data = {}
    for symbol, filename in FILES.items():
        if not Path(filename).exists():
            raise FileNotFoundError(f"Missing required data file: {filename}")
        frame = add_ichimoku_by_segment(add_indicators(load_data(filename)))
        data[symbol] = frame

    common_start = max(frame["timestamp"].min() for frame in data.values())
    common_end = min(frame["timestamp"].max() for frame in data.values())
    aligned = {}

    for symbol, frame in data.items():
        part = frame[
            (frame["timestamp"] >= common_start)
            & (frame["timestamp"] <= common_end)
        ].copy().sort_values("timestamp").reset_index(drop=True)
        aligned[symbol] = part

    reference_times = aligned[next(iter(aligned))]["timestamp"].reset_index(drop=True)
    for symbol, frame in aligned.items():
        times = frame["timestamp"].reset_index(drop=True)
        if not times.equals(reference_times):
            raise ValueError(f"Timestamp grids differ for {symbol}; refusing unfair comparison.")
        if not (times.diff().dropna() == pd.Timedelta(hours=4)).all():
            raise ValueError(f"Unexpected gap in common period for {symbol}.")

    return aligned, reference_times


def pooled_profit_factor(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    profit = float(trades.loc[trades["net_pnl"] > 0, "net_pnl"].sum())
    loss = float(abs(trades.loc[trades["net_pnl"] < 0, "net_pnl"].sum()))
    if loss > 0:
        return profit / loss
    return math.inf if profit > 0 else 0.0


def main():
    print("=" * 82)
    print("MABOT - ICHIMOKU ENTRY/EXIT COMPONENT TEST")
    print("Native Nobitex 4h candles | gap-aware | long-only spot")
    print("REAL TRADING: DISABLED")
    print(f"Assumed fee: {FEE_RATE * 100:.3f}% per side | slippage: {SLIPPAGE_RATE * 100:.3f}% per side")
    print("This test isolates entry and exit components; it does not tune parameters.")
    print("=" * 82)

    aligned, times = load_common_data()
    n = len(times)
    split = int(n * TRAIN_RATIO)
    start = WARMUP_BARS - 1
    if split <= start + 10 or n - split <= 10:
        raise ValueError("Insufficient data for the configured chronological split.")

    print(f"Common interval: {times.iloc[0]} -> {times.iloc[-1]}")
    print(f"Candles: {n} | training: {times.iloc[start]} -> {times.iloc[split - 1]}")
    print(f"Validation: {times.iloc[split]} -> {times.iloc[-1]}")
    print("NOTE: validation was inspected earlier; it is not a pristine holdout.")

    periods = {
        "TRAINING": (start, split),
        "VALIDATION": (split, n),
    }

    rows = []
    all_trades = []
    all_equity = []

    for period_name, (a, b) in periods.items():
        print(f"\n##### {period_name} #####")
        for symbol, frame in aligned.items():
            bh = buy_hold_return(frame, a, b)
            for strategy_name, buy_col, sell_col in STRATEGIES:
                result = backtest(frame, a, b, buy_col, sell_col)
                rows.append({
                    "period": period_name,
                    "symbol": symbol,
                    "strategy": strategy_name,
                    "return_pct": result["return_pct"],
                    "buy_hold_return_pct": bh,
                    "trades": result["trades"],
                    "win_rate_pct": result["win_rate_pct"],
                    "profit_factor": result["profit_factor"],
                    "max_drawdown_pct": result["max_drawdown_pct"],
                })

                detail = result["trade_details"].copy()
                if not detail.empty:
                    detail["period"] = period_name
                    detail["symbol"] = symbol
                    detail["strategy"] = strategy_name
                    all_trades.append(detail)

                curve = pd.DataFrame({
                    "timestamp": frame.iloc[a:b]["timestamp"].reset_index(drop=True),
                    "equity": result["equity"][1:],
                    "period": period_name,
                    "symbol": symbol,
                    "strategy": strategy_name,
                })
                all_equity.append(curve)

                print(
                    f"{symbol:4s} | {strategy_name:27s} | "
                    f"Return {result['return_pct']:8.2f}% | "
                    f"B&H {bh:8.2f}% | DD {result['max_drawdown_pct']:8.2f}% | "
                    f"Trades {result['trades']:3d} | Win {result['win_rate_pct']:5.1f}% | "
                    f"PF {result['profit_factor']:6.3f}"
                )

    report = pd.DataFrame(rows)
    report.to_csv("ichimoku_component_test_summary.csv", index=False)

    trade_report = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    if not trade_report.empty:
        trade_report.to_csv("ichimoku_component_test_trades.csv", index=False)

    aggregate_rows = []
    for (period_name, strategy_name), group in report.groupby(["period", "strategy"], sort=False):
        mask = (
            (trade_report["period"] == period_name)
            & (trade_report["strategy"] == strategy_name)
        ) if not trade_report.empty else pd.Series(dtype=bool)
        selected_trades = trade_report.loc[mask] if not trade_report.empty else pd.DataFrame()
        aggregate_rows.append({
            "period": period_name,
            "strategy": strategy_name,
            "average_return_pct": group["return_pct"].mean(),
            "median_return_pct": group["return_pct"].median(),
            "positive_markets": int((group["return_pct"] > 0).sum()),
            "average_buy_hold_pct": group["buy_hold_return_pct"].mean(),
            "average_drawdown_pct": group["max_drawdown_pct"].mean(),
            "total_trades": int(group["trades"].sum()),
            "average_win_rate_pct": group["win_rate_pct"].mean(),
            "pooled_profit_factor": pooled_profit_factor(selected_trades),
        })

    aggregate = pd.DataFrame(aggregate_rows)
    aggregate.to_csv("ichimoku_component_test_aggregate.csv", index=False)

    if all_equity:
        pd.concat(all_equity, ignore_index=True).to_csv(
            "ichimoku_component_test_equity.csv", index=False
        )

    print("\n" + "=" * 82)
    print("COMPONENT TEST AGGREGATE")
    print("=" * 82)
    print(aggregate.round(3).to_string(index=False))
    print("\nSaved: ichimoku_component_test_summary.csv")
    print("Saved: ichimoku_component_test_aggregate.csv")
    if not trade_report.empty:
        print("Saved: ichimoku_component_test_trades.csv")
    print("Saved: ichimoku_component_test_equity.csv")
    print("REAL TRADING: DISABLED")


if __name__ == "__main__":
    main()
