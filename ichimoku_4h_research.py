"""MABOT - Ichimoku 4h research

Compares BASELINE EMA/RSI, ADX-filtered EMA/RSI, and standard Ichimoku
(9, 26, 52) on the same common, gap-aware native 4h Nobitex data.
Long-only spot simulation. No API credentials and no real orders.

Ichimoku alignment is causal:
- Senkou spans are calculated from past data and shifted 26 bars to the
  chart position where the cloud is visible.
- Chikou confirmation is current close > close 26 bars ago.
- Signals from a completed candle execute at the next candle open.
"""

from pathlib import Path
import math
import numpy as np
import pandas as pd

from adx_4h_research import (
    FILES,
    INITIAL_CAPITAL,
    FEE_RATE,
    SLIPPAGE_RATE,
    TRAIN_RATIO,
    WARMUP_BARS,
    load_data,
    add_indicators,
)

ICHIMOKU_TENKAN = 9
ICHIMOKU_KIJUN = 26
ICHIMOKU_SENKOU_B = 52


def midrange(high: pd.Series, low: pd.Series, period: int) -> pd.Series:
    return (
        high.rolling(window=period, min_periods=period).max()
        + low.rolling(window=period, min_periods=period).min()
    ) / 2.0


def add_ichimoku_one_segment(part: pd.DataFrame) -> pd.DataFrame:
    part = part.copy()
    high = part["high"]
    low = part["low"]
    close = part["close"]

    tenkan = midrange(high, low, ICHIMOKU_TENKAN)
    kijun = midrange(high, low, ICHIMOKU_KIJUN)
    span_a_raw = (tenkan + kijun) / 2.0
    span_b_raw = midrange(high, low, ICHIMOKU_SENKOU_B)

    # Cloud values displayed at the current candle were calculated 26 bars ago.
    span_a_visible = span_a_raw.shift(ICHIMOKU_KIJUN)
    span_b_visible = span_b_raw.shift(ICHIMOKU_KIJUN)

    cloud_top = pd.concat(
        [span_a_visible, span_b_visible], axis=1
    ).max(axis=1, skipna=False)
    cloud_bottom = pd.concat(
        [span_a_visible, span_b_visible], axis=1
    ).min(axis=1, skipna=False)

    # Chikou confirmation without looking into the future.
    chikou_bullish = close > close.shift(ICHIMOKU_KIJUN)

    valid = pd.concat(
        [tenkan, kijun, span_a_visible, span_b_visible, chikou_bullish],
        axis=1,
    ).notna().all(axis=1)
    ready = (part["bars_in_segment"] >= WARMUP_BARS) & valid

    part["ICHIMOKU_TENKAN"] = tenkan
    part["ICHIMOKU_KIJUN"] = kijun
    part["ICHIMOKU_SPAN_A_VISIBLE"] = span_a_visible
    part["ICHIMOKU_SPAN_B_VISIBLE"] = span_b_visible
    part["ICHIMOKU_CLOUD_TOP"] = cloud_top
    part["ICHIMOKU_CLOUD_BOTTOM"] = cloud_bottom
    part["ICHIMOKU_CHIKOU_BULLISH"] = chikou_bullish

    part["BUY_ICHIMOKU"] = (
        ready
        & (close > cloud_top)
        & (tenkan > kijun)
        & chikou_bullish
    ).fillna(False)

    # Exit when price closes below the visible cloud or Tenkan is below Kijun.
    part["SELL_ICHIMOKU"] = (
        (close < cloud_bottom) | (tenkan < kijun)
    ).fillna(False)

    return part


def add_ichimoku_by_segment(df: pd.DataFrame) -> pd.DataFrame:
    chunks = []
    for _, segment in df.groupby("segment_id", sort=True):
        chunks.append(add_ichimoku_one_segment(segment))
    return pd.concat(chunks).sort_values("timestamp").reset_index(drop=True)


def backtest(
    df: pd.DataFrame,
    start: int,
    end: int,
    buy_column: str,
    sell_column: str,
) -> dict:
    cash = INITIAL_CAPITAL
    quantity = 0.0
    in_position = False
    invested = 0.0
    entry_time = None
    trades = []
    equity_points = [INITIAL_CAPITAL]
    previous_segment = None

    for i in range(start, end):
        row = df.iloc[i]
        segment_id = int(row["segment_id"])

        # Close at the last available close before any data discontinuity.
        if previous_segment is not None and segment_id != previous_segment:
            if in_position:
                prev_row = df.iloc[i - 1]
                exit_price = float(prev_row["close"]) * (1 - SLIPPAGE_RATE)
                cash = quantity * exit_price * (1 - FEE_RATE)
                trades.append({
                    "entry_time": entry_time,
                    "exit_time": prev_row["timestamp"],
                    "net_pnl": cash - invested,
                    "net_return_pct": (cash / invested - 1) * 100,
                    "exit_reason": "SEGMENT_END",
                })
                quantity = 0.0
                in_position = False
                entry_time = None
                equity_points[-1] = cash

        previous_segment = segment_id

        prev_row = df.iloc[i - 1] if i > 0 else None
        same_segment_previous = (
            prev_row is not None
            and int(prev_row["segment_id"]) == segment_id
        )
        buy_signal = bool(prev_row[buy_column]) if same_segment_previous else False
        sell_signal = bool(prev_row[sell_column]) if same_segment_previous else False

        open_price = float(row["open"])
        close_price = float(row["close"])

        if not in_position and buy_signal:
            entry_price = open_price * (1 + SLIPPAGE_RATE)
            invested = cash
            quantity = cash / (entry_price * (1 + FEE_RATE))
            cash = 0.0
            in_position = True
            entry_time = row["timestamp"]

        elif in_position and sell_signal:
            exit_price = open_price * (1 - SLIPPAGE_RATE)
            cash = quantity * exit_price * (1 - FEE_RATE)
            trades.append({
                "entry_time": entry_time,
                "exit_time": row["timestamp"],
                "net_pnl": cash - invested,
                "net_return_pct": (cash / invested - 1) * 100,
                "exit_reason": "SELL_SIGNAL",
            })
            quantity = 0.0
            in_position = False
            entry_time = None

        if in_position:
            marked_exit = close_price * (1 - SLIPPAGE_RATE)
            equity = quantity * marked_exit * (1 - FEE_RATE)
        else:
            equity = cash
        equity_points.append(equity)

    if in_position:
        last_row = df.iloc[end - 1]
        exit_price = float(last_row["close"]) * (1 - SLIPPAGE_RATE)
        cash = quantity * exit_price * (1 - FEE_RATE)
        trades.append({
            "entry_time": entry_time,
            "exit_time": last_row["timestamp"],
            "net_pnl": cash - invested,
            "net_return_pct": (cash / invested - 1) * 100,
            "exit_reason": "END_OF_PERIOD",
        })
        equity_points[-1] = cash

    eq = np.asarray(equity_points, dtype=float)
    peaks = np.maximum.accumulate(eq)
    max_dd = float(np.min((eq / peaks - 1) * 100)) if len(eq) else 0.0

    trade_df = pd.DataFrame(trades)
    if not trade_df.empty:
        wins = trade_df.loc[trade_df["net_pnl"] > 0, "net_pnl"]
        losses = trade_df.loc[trade_df["net_pnl"] < 0, "net_pnl"]
        gross_profit = float(wins.sum())
        gross_loss = float(abs(losses.sum()))
        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = math.inf
        else:
            profit_factor = 0.0
        win_rate = float((trade_df["net_pnl"] > 0).mean() * 100)
    else:
        profit_factor = 0.0
        win_rate = 0.0

    return {
        "final_capital": float(cash),
        "return_pct": (float(cash) / INITIAL_CAPITAL - 1) * 100,
        "trades": len(trade_df),
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_dd,
        "trade_details": trade_df,
        "equity": eq,
    }


def buy_hold_return(df: pd.DataFrame, start: int, end: int) -> float:
    first_open = float(df.iloc[start]["open"])
    last_close = float(df.iloc[end - 1]["close"])
    buy_price = first_open * (1 + SLIPPAGE_RATE)
    sell_price = last_close * (1 - SLIPPAGE_RATE)
    qty = INITIAL_CAPITAL / (buy_price * (1 + FEE_RATE))
    final_value = qty * sell_price * (1 - FEE_RATE)
    return (final_value / INITIAL_CAPITAL - 1) * 100


def main() -> None:
    print("=" * 78)
    print("MABOT - ICHIMOKU 4H RESEARCH | REAL TRADING: DISABLED")
    print(
        f"Assumed fee {FEE_RATE * 100:.3f}% and slippage "
        f"{SLIPPAGE_RATE * 100:.3f}% per side"
    )
    print("Ichimoku parameters fixed at 9 / 26 / 52; no parameter sweep")
    print("Signals use completed candles and execute at the next candle open")
    print("=" * 78)

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

    base_times = aligned[next(iter(aligned))]["timestamp"].reset_index(drop=True)
    for symbol, frame in aligned.items():
        times = frame["timestamp"].reset_index(drop=True)
        if not times.equals(base_times):
            raise ValueError(
                f"Timestamp grids are not identical for {symbol}; inspect gap audit."
            )
        if not (times.diff().dropna() == pd.Timedelta(hours=4)).all():
            raise ValueError(
                f"A discontinuity exists inside the common interval for {symbol}."
            )

    n = len(base_times)
    split = int(n * TRAIN_RATIO)
    train_start = WARMUP_BARS - 1
    if split <= train_start + 10 or n - split <= 10:
        raise ValueError("Insufficient candles for chronological train/validation split.")

    print(f"Common period: {base_times.iloc[0]} -> {base_times.iloc[-1]}")
    print(f"Common 4h candles: {n}; training begins after {WARMUP_BARS} bars")
    print(f"Training: {base_times.iloc[train_start]} -> {base_times.iloc[split - 1]}")
    print(f"Validation: {base_times.iloc[split]} -> {base_times.iloc[-1]}")
    print("NOTE: validation was previously inspected; it is not a pristine holdout.")

    strategies = [
        ("BASELINE", "BUY_BASELINE", "SELL_SIGNAL"),
        ("ADX20_PLUS_DI", "BUY_ADX", "SELL_SIGNAL"),
        ("ICHIMOKU_9_26_52", "BUY_ICHIMOKU", "SELL_ICHIMOKU"),
    ]
    periods = {
        "TRAINING": (train_start, split),
        "VALIDATION": (split, n),
    }

    summary_rows = []
    all_trades = []
    all_equity = []

    for period_name, (start, end) in periods.items():
        print(f"\n##### {period_name} #####")
        for symbol, frame in aligned.items():
            buy_hold = buy_hold_return(frame, start, end)
            for strategy_name, buy_col, sell_col in strategies:
                result = backtest(frame, start, end, buy_col, sell_col)
                summary_rows.append({
                    "period": period_name,
                    "symbol": symbol,
                    "strategy": strategy_name,
                    "return_pct": result["return_pct"],
                    "buy_hold_return_pct": buy_hold,
                    "trades": result["trades"],
                    "win_rate_pct": result["win_rate_pct"],
                    "profit_factor": result["profit_factor"],
                    "max_drawdown_pct": result["max_drawdown_pct"],
                })
                if not result["trade_details"].empty:
                    trades = result["trade_details"].copy()
                    trades["period"] = period_name
                    trades["symbol"] = symbol
                    trades["strategy"] = strategy_name
                    all_trades.append(trades)
                equity = pd.DataFrame({
                    "timestamp": frame.iloc[start:end]["timestamp"].reset_index(drop=True),
                    "equity": result["equity"][1:],
                })
                equity["period"] = period_name
                equity["symbol"] = symbol
                equity["strategy"] = strategy_name
                all_equity.append(equity)

                print(
                    f"{symbol:4s} | {strategy_name:17s} | "
                    f"Return {result['return_pct']:8.2f}% | "
                    f"B&H {buy_hold:8.2f}% | "
                    f"DD {result['max_drawdown_pct']:8.2f}% | "
                    f"Trades {result['trades']:3d} | "
                    f"Win {result['win_rate_pct']:6.1f}% | "
                    f"PF {result['profit_factor']:6.3f}"
                )

    report = pd.DataFrame(summary_rows)
    report.to_csv("ichimoku_4h_research_summary.csv", index=False)

    aggregate = report.groupby(["period", "strategy"]).agg(
        average_return_pct=("return_pct", "mean"),
        median_return_pct=("return_pct", "median"),
        positive_markets=("return_pct", lambda x: int((x > 0).sum())),
        average_buy_hold_pct=("buy_hold_return_pct", "mean"),
        average_drawdown_pct=("max_drawdown_pct", "mean"),
        total_trades=("trades", "sum"),
        average_win_rate_pct=("win_rate_pct", "mean"),
    ).reset_index()

    if all_trades:
        trade_report = pd.concat(all_trades, ignore_index=True)
        pooled_pf = {}
        for (period_name, strategy_name), group in trade_report.groupby(["period", "strategy"]):
            gross_profit = float(group.loc[group["net_pnl"] > 0, "net_pnl"].sum())
            gross_loss = float(abs(group.loc[group["net_pnl"] < 0, "net_pnl"].sum()))
            pooled_pf[(period_name, strategy_name)] = (
                gross_profit / gross_loss if gross_loss > 0
                else math.inf if gross_profit > 0 else 0.0
            )
        aggregate["pooled_profit_factor"] = aggregate.apply(
            lambda row: pooled_pf.get((row["period"], row["strategy"]), 0.0),
            axis=1,
        )
        trade_report.to_csv("ichimoku_4h_research_trades.csv", index=False)

    aggregate.to_csv("ichimoku_4h_research_aggregate.csv", index=False)
    if all_equity:
        pd.concat(all_equity, ignore_index=True).to_csv(
            "ichimoku_4h_research_equity.csv", index=False
        )

    print("\n" + "=" * 78)
    print("AGGREGATE RESULTS")
    print("=" * 78)
    print(aggregate.round(3).to_string(index=False))
    print("\nSaved: ichimoku_4h_research_summary.csv")
    print("Saved: ichimoku_4h_research_aggregate.csv")
    if all_trades:
        print("Saved: ichimoku_4h_research_trades.csv")
    print("Saved: ichimoku_4h_research_equity.csv")
    print("REAL TRADING: DISABLED")


if __name__ == "__main__":
    main()
