"""MABOT - 4h ADX filter research

Reads the gap-aware native 4h Nobitex CSVs created by
prepare_gap_aware_data.py. Never modifies source data and never places orders.

Compares:
  1) BASELINE: EMA20 > EMA50 and RSI14 > 50
  2) ADX_FILTER: baseline entry plus ADX14 >= 20 and +DI > -DI

Exit logic is identical for both: EMA20 < EMA50 or RSI14 < 45.
Signals are evaluated on the prior completed candle and executed at the
next candle open. Indicators restart independently in each continuous segment.
"""

from pathlib import Path
import math
import numpy as np
import pandas as pd

INITIAL_CAPITAL = 100.0
FEE_RATE = 0.002       # assumption: 0.20% per side; verify actual Nobitex tier
SLIPPAGE_RATE = 0.0005 # assumption: 0.05% per side
ADX_THRESHOLD = 20.0  # fixed in advance for this first diagnostic
TRAIN_RATIO = 0.70
WARMUP_BARS = 200

FILES = {
    "BTC": "btcusdt_4h_native_gap_aware.csv",
    "ETH": "ethusdt_4h_native_gap_aware.csv",
    "ZEC": "zecusdt_4h_native_gap_aware.csv",
    "XRP": "xrpusdt_4h_native_gap_aware.csv",
}


def load_data(filename: str) -> pd.DataFrame:
    path = Path(filename)
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {filename}")

    df = pd.read_csv(path)
    required = {
        "timestamp", "open", "high", "low", "close", "volume",
        "segment_id", "bars_in_segment"
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{filename} is missing columns: {', '.join(sorted(missing))}. "
            "Run prepare_gap_aware_data.py first."
        )

    if pd.api.types.is_numeric_dtype(df["timestamp"]):
        df["timestamp"] = pd.to_datetime(
            df["timestamp"], unit="s", utc=True, errors="coerce"
        )
    else:
        df["timestamp"] = pd.to_datetime(
            df["timestamp"], utc=True, errors="coerce"
        )

    numeric = ["open", "high", "low", "close", "volume", "segment_id", "bars_in_segment"]
    for col in numeric:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df["timestamp"].isna().any() or df[numeric].isna().any().any():
        raise ValueError(f"{filename} contains invalid timestamps or numeric values")
    if df["timestamp"].duplicated().any():
        raise ValueError(f"{filename} contains duplicate timestamps")

    df = df.sort_values("timestamp").reset_index(drop=True)
    if not df["timestamp"].is_monotonic_increasing:
        raise ValueError(f"{filename} timestamps are not sorted")

    # Validate OHLC consistency before research.
    invalid = (
        (df["high"] < df["low"]) |
        (df["high"] < df["open"]) |
        (df["high"] < df["close"]) |
        (df["low"] > df["open"]) |
        (df["low"] > df["close"]) |
        (df["volume"] < 0)
    )
    if invalid.any():
        raise ValueError(f"{filename} contains invalid OHLC/volume rows")

    return df


def wilder_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(
        alpha=1.0 / period,
        adjust=False,
        min_periods=period
    ).mean()


def add_indicators_one_segment(part: pd.DataFrame) -> pd.DataFrame:
    part = part.copy()
    close = part["close"]
    high = part["high"]
    low = part["low"]

    part["EMA20"] = close.ewm(span=20, adjust=False).mean()
    part["EMA50"] = close.ewm(span=50, adjust=False).mean()

    # RSI-14 (Wilder smoothing)
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = wilder_ema(gains, 14)
    avg_loss = wilder_ema(losses, 14)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100)
    rsi = rsi.mask((avg_loss == 0) & (avg_gain == 0), 50)
    part["RSI14"] = rsi

    # ADX-14 and directional indicators, calculated within this segment only.
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=part.index,
        dtype="float64"
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=part.index,
        dtype="float64"
    )

    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1
    ).max(axis=1)

    atr14 = wilder_ema(tr, 14)
    plus_smoothed = wilder_ema(plus_dm, 14)
    minus_smoothed = wilder_ema(minus_dm, 14)

    plus_di = 100 * plus_smoothed / atr14.replace(0, np.nan)
    minus_di = 100 * minus_smoothed / atr14.replace(0, np.nan)
    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / di_sum
    adx = wilder_ema(dx, 14)

    part["ATR14"] = atr14
    part["PLUS_DI14"] = plus_di
    part["MINUS_DI14"] = minus_di
    part["ADX14"] = adx

    # Require a 200-bar warm-up within each uninterrupted segment.
    ready = part["bars_in_segment"] >= WARMUP_BARS
    valid_indicators = part[["EMA20", "EMA50", "RSI14", "ADX14", "PLUS_DI14", "MINUS_DI14"]].notna().all(axis=1)
    ready = ready & valid_indicators

    base_buy = (part["EMA20"] > part["EMA50"]) & (part["RSI14"] > 50)
    part["BUY_BASELINE"] = (ready & base_buy).fillna(False)
    part["BUY_ADX"] = (
        ready
        & base_buy
        & (part["ADX14"] >= ADX_THRESHOLD)
        & (part["PLUS_DI14"] > part["MINUS_DI14"])
    ).fillna(False)

    # Identical exit signal for both variants.
    part["SELL_SIGNAL"] = (
        (part["EMA20"] < part["EMA50"]) |
        (part["RSI14"] < 45)
    ).fillna(False)

    return part


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    pieces = []
    for _, part in df.groupby("segment_id", sort=True):
        pieces.append(add_indicators_one_segment(part))
    return pd.concat(pieces).sort_values("timestamp").reset_index(drop=True)


def backtest(df: pd.DataFrame, start: int, end: int, buy_column: str) -> dict:
    cash = INITIAL_CAPITAL
    quantity = 0.0
    in_position = False
    invested = 0.0
    trades = []
    equity_points = [INITIAL_CAPITAL]
    previous_segment = None

    for i in range(start, end):
        row = df.iloc[i]
        segment = int(row["segment_id"])

        # Never carry a position or a signal across a data discontinuity.
        if previous_segment is not None and segment != previous_segment:
            if in_position:
                prev_row = df.iloc[i - 1]
                exit_price = float(prev_row["close"]) * (1 - SLIPPAGE_RATE)
                cash = quantity * exit_price * (1 - FEE_RATE)
                trades.append({
                    "net_pnl": cash - invested,
                    "net_return_pct": (cash / invested - 1) * 100,
                    "exit_reason": "SEGMENT_END",
                    "exit_time": prev_row["timestamp"],
                })
                quantity = 0.0
                in_position = False
                equity_points[-1] = cash

        previous_segment = segment

        # Need a previous candle from the same continuous segment.
        prev_row = df.iloc[i - 1] if i > 0 else None
        same_segment_previous = (
            prev_row is not None and int(prev_row["segment_id"]) == segment
        )

        if same_segment_previous:
            buy_signal = bool(prev_row[buy_column])
            sell_signal = bool(prev_row["SELL_SIGNAL"])
        else:
            buy_signal = False
            sell_signal = False

        open_price = float(row["open"])
        close_price = float(row["close"])

        if not in_position and buy_signal:
            entry_price = open_price * (1 + SLIPPAGE_RATE)
            invested = cash
            quantity = cash / (entry_price * (1 + FEE_RATE))
            cash = 0.0
            in_position = True

        elif in_position and sell_signal:
            exit_price = open_price * (1 - SLIPPAGE_RATE)
            cash = quantity * exit_price * (1 - FEE_RATE)
            net_pnl = cash - invested
            trades.append({
                "net_pnl": net_pnl,
                "net_return_pct": (cash / invested - 1) * 100,
                "exit_reason": "SELL_SIGNAL",
                "exit_time": row["timestamp"],
            })
            quantity = 0.0
            in_position = False

        if in_position:
            marked_exit = close_price * (1 - SLIPPAGE_RATE)
            equity = quantity * marked_exit * (1 - FEE_RATE)
        else:
            equity = cash

        equity_points.append(equity)

    # Close any open position at the end of this research window.
    if in_position:
        last_row = df.iloc[end - 1]
        exit_price = float(last_row["close"]) * (1 - SLIPPAGE_RATE)
        cash = quantity * exit_price * (1 - FEE_RATE)
        trades.append({
            "net_pnl": cash - invested,
            "net_return_pct": (cash / invested - 1) * 100,
            "exit_reason": "END_OF_PERIOD",
            "exit_time": last_row["timestamp"],
        })
        equity_points[-1] = cash

    eq = np.asarray(equity_points, dtype=float)
    peaks = np.maximum.accumulate(eq)
    dd = np.min((eq / peaks - 1) * 100) if len(eq) else 0.0

    trade_df = pd.DataFrame(trades)
    if len(trade_df):
        wins = trade_df.loc[trade_df["net_pnl"] > 0, "net_pnl"]
        losses = trade_df.loc[trade_df["net_pnl"] < 0, "net_pnl"]
        gross_profit = float(wins.sum())
        gross_loss = float(abs(losses.sum()))
        if gross_loss > 0:
            pf = gross_profit / gross_loss
        elif gross_profit > 0:
            pf = math.inf
        else:
            pf = 0.0
        win_rate = float((trade_df["net_pnl"] > 0).mean() * 100)
    else:
        pf = 0.0
        win_rate = 0.0

    return {
        "final_capital": float(cash),
        "return_pct": (float(cash) / INITIAL_CAPITAL - 1) * 100,
        "trades": len(trade_df),
        "win_rate_pct": win_rate,
        "profit_factor": pf,
        "max_drawdown_pct": float(dd),
        "trade_details": trade_df,
        "equity": eq,
    }


def buy_hold_return(df: pd.DataFrame, start: int, end: int) -> float:
    first_open = float(df.iloc[start]["open"])
    last_close = float(df.iloc[end - 1]["close"])
    buy_price = first_open * (1 + SLIPPAGE_RATE)
    sell_price = last_close * (1 - SLIPPAGE_RATE)
    qty = INITIAL_CAPITAL / (buy_price * (1 + FEE_RATE))
    final = qty * sell_price * (1 - FEE_RATE)
    return (final / INITIAL_CAPITAL - 1) * 100


def main() -> None:
    print("=" * 76)
    print("MABOT - 4H ADX FILTER RESEARCH")
    print("Native Nobitex candles | gap-aware indicators | long-only spot")
    print("REAL TRADING: DISABLED")
    print(f"Assumed fee: {FEE_RATE * 100:.3f}% per side | assumed slippage: {SLIPPAGE_RATE * 100:.3f}% per side")
    print(f"ADX threshold fixed at {ADX_THRESHOLD:.1f}; no parameter sweep")
    print("=" * 76)

    data = {symbol: add_indicators(load_data(filename)) for symbol, filename in FILES.items()}

    # Use a common timestamp range across all four markets.
    common_start = max(frame["timestamp"].min() for frame in data.values())
    common_end = min(frame["timestamp"].max() for frame in data.values())
    aligned = {}
    for symbol, frame in data.items():
        part = frame[(frame["timestamp"] >= common_start) & (frame["timestamp"] <= common_end)].copy()
        part = part.sort_values("timestamp").reset_index(drop=True)
        aligned[symbol] = part

    # Require identical 4h timestamp grids after the common start. Do not silently
    # compare different periods if a symbol has additional missing candles.
    base_times = aligned[next(iter(aligned))]["timestamp"].reset_index(drop=True)
    for symbol, frame in aligned.items():
        times = frame["timestamp"].reset_index(drop=True)
        if not times.equals(base_times):
            raise ValueError(
                f"Timestamp grids are not identical for {symbol}. "
                "Inspect gap audit before running a cross-market comparison."
            )
        deltas = times.diff().dropna()
        if not (deltas == pd.Timedelta(hours=4)).all():
            raise ValueError(
                f"A discontinuity exists inside the common period for {symbol}. "
                "Do not bridge it; review the gap-aware files."
            )

    n = len(base_times)
    if n <= WARMUP_BARS + 20:
        raise ValueError("Not enough common candles after warm-up.")

    # Keep a common initial warm-up; training and validation are split by time.
    split = int(n * TRAIN_RATIO)
    train_start = WARMUP_BARS - 1
    if split <= train_start + 10 or n - split <= 10:
        raise ValueError("Insufficient data for the requested chronological split.")

    print(f"Common period: {base_times.iloc[0]} -> {base_times.iloc[-1]}")
    print(f"Common 4h candles: {n} | training starts after {WARMUP_BARS} common bars")
    print(f"Training window: {base_times.iloc[train_start]} -> {base_times.iloc[split - 1]}")
    print(f"Validation window: {base_times.iloc[split]} -> {base_times.iloc[-1]}")
    print("NOTE: this validation slice has been viewed in earlier project analysis; it is not a pristine final holdout.")

    rows = []
    all_trades = []
    all_equity = []

    strategies = {
        "BASELINE": "BUY_BASELINE",
        "ADX20_PLUS_DI": "BUY_ADX",
    }
    periods = {
        "TRAINING": (train_start, split),
        "VALIDATION": (split, n),
    }

    for period_name, (start, end) in periods.items():
        print(f"\n##### {period_name} #####")
        for symbol, frame in aligned.items():
            for strategy_name, buy_col in strategies.items():
                result = backtest(frame, start, end, buy_col)
                bh = buy_hold_return(frame, start, end)
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
                if not result["trade_details"].empty:
                    td = result["trade_details"].copy()
                    td["period"] = period_name
                    td["symbol"] = symbol
                    td["strategy"] = strategy_name
                    all_trades.append(td)
                eq = pd.DataFrame({
                    "timestamp": frame.iloc[start:end]["timestamp"].reset_index(drop=True),
                    "equity": result["equity"][1:],
                })
                eq["period"] = period_name
                eq["symbol"] = symbol
                eq["strategy"] = strategy_name
                all_equity.append(eq)

                print(
                    f"{symbol:4s} | {strategy_name:14s} | "
                    f"Return {result['return_pct']:8.2f}% | "
                    f"B&H {bh:8.2f}% | "
                    f"DD {result['max_drawdown_pct']:8.2f}% | "
                    f"Trades {result['trades']:3d} | "
                    f"Win {result['win_rate_pct']:6.1f}% | "
                    f"PF {result['profit_factor']:6.3f}"
                )

    report = pd.DataFrame(rows)
    report.to_csv("adx_4h_research_summary.csv", index=False)

    aggregate = report.groupby(["period", "strategy"]).agg(
        average_return_pct=("return_pct", "mean"),
        median_return_pct=("return_pct", "median"),
        positive_markets=("return_pct", lambda x: int((x > 0).sum())),
        average_buy_hold_pct=("buy_hold_return_pct", "mean"),
        average_drawdown_pct=("max_drawdown_pct", "mean"),
        total_trades=("trades", "sum"),
        average_win_rate_pct=("win_rate_pct", "mean"),
    ).reset_index()

    # Pooled profit factor is computed from actual trade PnL, not average of market PFs.
    if all_trades:
        trade_report = pd.concat(all_trades, ignore_index=True)
        pooled = {}
        for (period_name, strategy_name), group in trade_report.groupby(["period", "strategy"]):
            gp = float(group.loc[group["net_pnl"] > 0, "net_pnl"].sum())
            gl = float(abs(group.loc[group["net_pnl"] < 0, "net_pnl"].sum()))
            pooled[(period_name, strategy_name)] = gp / gl if gl > 0 else (math.inf if gp > 0 else 0.0)
        aggregate["pooled_profit_factor"] = aggregate.apply(
            lambda row: pooled.get((row["period"], row["strategy"]), 0.0),
            axis=1
        )
        trade_report.to_csv("adx_4h_research_trades.csv", index=False)
    else:
        trade_report = pd.DataFrame()

    aggregate.to_csv("adx_4h_research_aggregate.csv", index=False)
    if all_equity:
        pd.concat(all_equity, ignore_index=True).to_csv(
            "adx_4h_research_equity.csv", index=False
        )

    print("\n" + "=" * 76)
    print("AGGREGATE RESULTS")
    print("=" * 76)
    print(aggregate.round(3).to_string(index=False))
    print("\nSaved: adx_4h_research_summary.csv")
    print("Saved: adx_4h_research_aggregate.csv")
    if all_trades:
        print("Saved: adx_4h_research_trades.csv")
    if all_equity:
        print("Saved: adx_4h_research_equity.csv")
    print("\nResearch only. REAL TRADING: DISABLED")


if __name__ == "__main__":
    main()
