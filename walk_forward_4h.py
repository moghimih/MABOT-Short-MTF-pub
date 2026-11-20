"""MABOT - Walk-forward stability test for native 4h spot strategies.

Research only. No API keys, no orders, no parameter optimization.
Uses fixed BASELINE and ICHIMOKU rules already defined in the project.
Six calendar months are reserved as initial history/warm-up; then the
remaining period is evaluated in consecutive two-month out-of-sample folds.
Each fold starts flat and any open position is closed at that fold's last close.
"""

import math
import pandas as pd

from adx_4h_research import (
    FILES,
    FEE_RATE,
    SLIPPAGE_RATE,
    load_data,
    add_indicators,
)
from ichimoku_4h_research import (
    INITIAL_CAPITAL,
    add_ichimoku_by_segment,
    backtest,
    buy_hold_return,
)

INITIAL_HISTORY_MONTHS = 6
TEST_MONTHS = 2
MIN_FINAL_FOLD_DAYS = 30

STRATEGIES = [
    ("BASELINE", "BUY_BASELINE", "SELL_SIGNAL"),
    ("ICHIMOKU_9_26_52", "BUY_ICHIMOKU", "SELL_ICHIMOKU"),
]


def load_all_markets():
    data = {}
    for symbol, filename in FILES.items():
        raw = load_data(filename)
        with_indicators = add_indicators(raw)
        data[symbol] = add_ichimoku_by_segment(with_indicators)

    common_start = max(frame["timestamp"].min() for frame in data.values())
    common_end = min(frame["timestamp"].max() for frame in data.values())

    aligned = {}
    for symbol, frame in data.items():
        part = frame[
            (frame["timestamp"] >= common_start)
            & (frame["timestamp"] <= common_end)
        ].copy().sort_values("timestamp").reset_index(drop=True)
        aligned[symbol] = part

    base_times = aligned[next(iter(aligned))]["timestamp"]
    for symbol, frame in aligned.items():
        times = frame["timestamp"]
        if not times.reset_index(drop=True).equals(
            base_times.reset_index(drop=True)
        ):
            raise ValueError(
                f"{symbol}: timestamp grid differs from the other markets."
            )
        if not (times.diff().dropna() == pd.Timedelta(hours=4)).all():
            raise ValueError(
                f"{symbol}: a time gap exists in the common comparison range."
            )

    return aligned, common_start, common_end


def build_folds(times):
    first_test = times.iloc[0] + pd.DateOffset(months=INITIAL_HISTORY_MONTHS)
    folds = []
    fold_start = first_test
    fold_number = 1

    while fold_start < times.iloc[-1]:
        fold_end = fold_start + pd.DateOffset(months=TEST_MONTHS)
        start_idx = int(times.searchsorted(fold_start, side="left"))
        end_idx = int(times.searchsorted(fold_end, side="left"))

        if end_idx > len(times):
            end_idx = len(times)

        if start_idx >= len(times):
            break

        actual_start = times.iloc[start_idx]
        actual_end = times.iloc[end_idx - 1] if end_idx > start_idx else actual_start
        actual_days = (actual_end - actual_start).total_seconds() / 86400

        if end_idx > start_idx and actual_days >= MIN_FINAL_FOLD_DAYS:
            folds.append((fold_number, start_idx, end_idx, actual_start, actual_end))
            fold_number += 1

        fold_start = fold_end

    return folds


def main():
    print("=" * 78)
    print("MABOT - WALK-FORWARD 4H STABILITY TEST")
    print("Native Nobitex candles | long-only spot | real trading DISABLED")
    print(
        f"Assumed costs: fee {FEE_RATE * 100:.3f}% + slippage "
        f"{SLIPPAGE_RATE * 100:.3f}% per side"
    )
    print(
        f"Initial history: {INITIAL_HISTORY_MONTHS} months | "
        f"test folds: {TEST_MONTHS} months"
    )
    print("No parameter tuning. Fixed strategy rules only.")
    print("=" * 78)

    aligned, common_start, common_end = load_all_markets()
    times = aligned[next(iter(aligned))]["timestamp"]
    folds = build_folds(times)

    print(f"Common data: {common_start} -> {common_end}")
    print(f"Common candles: {len(times)}")
    print(f"Out-of-sample folds created: {len(folds)}")

    if not folds:
        raise ValueError("No eligible test folds. Check available history.")

    summary_rows = []
    trade_rows = []

    for fold_no, start, end, fold_start, fold_end in folds:
        print(
            f"\n--- FOLD {fold_no}: {fold_start} -> {fold_end} "
            f"({end - start} candles) ---"
        )

        for symbol, frame in aligned.items():
            bh = buy_hold_return(frame, start, end)

            for strategy_name, buy_col, sell_col in STRATEGIES:
                result = backtest(
                    frame,
                    start,
                    end,
                    buy_column=buy_col,
                    sell_column=sell_col,
                )

                summary_rows.append({
                    "fold": fold_no,
                    "test_start": fold_start,
                    "test_end": fold_end,
                    "symbol": symbol,
                    "strategy": strategy_name,
                    "return_pct": result["return_pct"],
                    "buy_hold_return_pct": bh,
                    "trades": result["trades"],
                    "win_rate_pct": result["win_rate_pct"],
                    "profit_factor": result["profit_factor"],
                    "max_drawdown_pct": result["max_drawdown_pct"],
                    "final_capital": result["final_capital"],
                })

                trades = result["trade_details"]
                if not trades.empty:
                    saved = trades.copy()
                    saved["fold"] = fold_no
                    saved["symbol"] = symbol
                    saved["strategy"] = strategy_name
                    trade_rows.append(saved)

                print(
                    f"{symbol:4s} | {strategy_name:17s} | "
                    f"Return {result['return_pct']:8.2f}% | "
                    f"B&H {bh:8.2f}% | "
                    f"DD {result['max_drawdown_pct']:8.2f}% | "
                    f"Trades {result['trades']:3d} | "
                    f"Win {result['win_rate_pct']:6.1f}% | "
                    f"PF {result['profit_factor']:6.3f}"
                )

    report = pd.DataFrame(summary_rows)
    report.to_csv("walk_forward_4h_summary.csv", index=False)

    aggregate = report.groupby("strategy").agg(
        fold_market_observations=("return_pct", "count"),
        average_return_pct=("return_pct", "mean"),
        median_return_pct=("return_pct", "median"),
        positive_observations=("return_pct", lambda x: int((x > 0).sum())),
        average_buy_hold_pct=("buy_hold_return_pct", "mean"),
        average_drawdown_pct=("max_drawdown_pct", "mean"),
        total_trades=("trades", "sum"),
        average_win_rate_pct=("win_rate_pct", "mean"),
    ).reset_index()

    if trade_rows:
        all_trades = pd.concat(trade_rows, ignore_index=True)
        pooled_rows = []
        for strategy_name, group in all_trades.groupby("strategy"):
            gross_profit = float(group.loc[group["net_pnl"] > 0, "net_pnl"].sum())
            gross_loss = float(abs(group.loc[group["net_pnl"] < 0, "net_pnl"].sum()))
            pf = (
                gross_profit / gross_loss
                if gross_loss > 0
                else math.inf if gross_profit > 0
                else 0.0
            )
            pooled_rows.append({
                "strategy": strategy_name,
                "pooled_profit_factor": pf,
            })
        aggregate = aggregate.merge(pd.DataFrame(pooled_rows), on="strategy", how="left")
        all_trades.to_csv("walk_forward_4h_trades.csv", index=False)

    aggregate.to_csv("walk_forward_4h_aggregate.csv", index=False)

    print("\n" + "=" * 78)
    print("WALK-FORWARD AGGREGATE")
    print("=" * 78)
    print(aggregate.round(3).to_string(index=False))
    print("\nSaved:")
    print("walk_forward_4h_summary.csv")
    print("walk_forward_4h_aggregate.csv")
    if trade_rows:
        print("walk_forward_4h_trades.csv")

    print("\nIMPORTANT:")
    print("- These are sequential test windows, not proof of future profitability.")
    print("- Earlier project analysis has already inspected parts of this dataset.")
    print("- No live trading or API order placement was performed.")


if __name__ == "__main__":
    main()
