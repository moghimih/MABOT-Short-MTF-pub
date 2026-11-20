"""Forward-path diagnostics for BUY signals; research only, no orders.

For each BUY signal, the hypothetical entry is the next candle open (with
configured slippage). Returns use the close after 1/3/5/10/20 bars. MFE/MAE
use highs/lows from the entry candle through the horizon. Samples are
opportunity-level and may overlap; they are not a portfolio backtest.
"""

from pathlib import Path
import pandas as pd

from config.settings import FEE_RATE, SLIPPAGE_RATE
from data.loader import load_all_markets
from indicators.engine import calculate_all_indicators
from strategies.baseline import BaselineStrategy
from strategies.adx_strategy import ADXStrategy
from strategies.breakout import BreakoutStrategy

START = pd.Timestamp("2025-07-07 16:30:00+00:00")
END = pd.Timestamp("2026-11-16 12:30:00+00:00")
HORIZONS = (1, 3, 5, 10, 20)
OUT = Path("results")


def prepare_common_data():
    raw = load_all_markets()
    sliced = {}
    timestamp_sets = {}
    for symbol, frame in raw.items():
        part = frame.copy()
        part["timestamp"] = pd.to_datetime(part["timestamp"], utc=True)
        part = part.loc[part["timestamp"].between(START, END)].copy()
        part = part.sort_values("timestamp").reset_index(drop=True)
        sliced[symbol] = part
        timestamp_sets[symbol] = set(part["timestamp"])
    common = sorted(set.intersection(*timestamp_sets.values()))
    if not common:
        raise RuntimeError("No common timestamps available")
    for symbol, frame in sliced.items():
        frame = frame.loc[frame["timestamp"].isin(common)].copy()
        frame = frame.sort_values("timestamp").reset_index(drop=True)
        frame["bars_in_segment"] = frame.groupby("segment_id", sort=False).cumcount() + 1
        sliced[symbol] = frame
    return sliced


def evaluate_symbol(symbol, frame, strategy_name, strategy):
    enriched = calculate_all_indicators(frame)
    signals = strategy.generate_signals(enriched)
    rows = []
    for entry_idx in range(1, len(frame)):
        signal_idx = entry_idx - 1
        if not bool(signals.iloc[signal_idx]["BUY"]):
            continue
        if frame.iloc[signal_idx]["segment_id"] != frame.iloc[entry_idx]["segment_id"]:
            continue
        entry_bar = frame.iloc[entry_idx]
        entry = float(entry_bar["open"]) * (1 + SLIPPAGE_RATE)
        for horizon in HORIZONS:
            end_idx = entry_idx + horizon - 1
            if end_idx >= len(frame):
                continue
            window = frame.iloc[entry_idx:end_idx + 1]
            if window["segment_id"].nunique() != 1:
                continue
            exit_price = float(frame.iloc[end_idx]["close"]) * (1 - SLIPPAGE_RATE)
            net_exit = exit_price * (1 - FEE_RATE)
            net_entry = entry * (1 + FEE_RATE)
            net_return = (net_exit / net_entry - 1) * 100
            rows.append({
                "symbol": symbol,
                "strategy": strategy_name,
                "signal_time": frame.iloc[signal_idx]["timestamp"],
                "entry_time": entry_bar["timestamp"],
                "horizon_bars": horizon,
                "net_return_pct": net_return,
                "mfe_pct": (float(window["high"].max()) / entry - 1) * 100,
                "mae_pct": (float(window["low"].min()) / entry - 1) * 100,
            })
    return rows


def main():
    OUT.mkdir(exist_ok=True)
    strategies = {
        "BASELINE": BaselineStrategy(),
        "ADX": ADXStrategy(),
        "BREAKOUT": BreakoutStrategy(),
    }
    markets = prepare_common_data()
    records = []
    for symbol, frame in markets.items():
        for name, strategy in strategies.items():
            records.extend(evaluate_symbol(symbol, frame, name, strategy))
    detail = pd.DataFrame(records)
    if detail.empty:
        raise RuntimeError("No eligible forward samples found")
    detail.to_csv(OUT / "forward_entry_diagnostics.csv", index=False)
    summary = detail.groupby(["strategy", "symbol", "horizon_bars"], as_index=False).agg(
        samples=("net_return_pct", "size"),
        win_rate_pct=("net_return_pct", lambda x: (x > 0).mean() * 100),
        mean_net_return_pct=("net_return_pct", "mean"),
        median_net_return_pct=("net_return_pct", "median"),
        mean_mfe_pct=("mfe_pct", "mean"),
        mean_mae_pct=("mae_pct", "mean"),
    )
    summary.to_csv(OUT / "forward_entry_summary.csv", index=False)
    pooled = detail.groupby(["strategy", "horizon_bars"], as_index=False).agg(
        samples=("net_return_pct", "size"),
        win_rate_pct=("net_return_pct", lambda x: (x > 0).mean() * 100),
        mean_net_return_pct=("net_return_pct", "mean"),
        median_net_return_pct=("net_return_pct", "median"),
        mean_mfe_pct=("mfe_pct", "mean"),
        mean_mae_pct=("mae_pct", "mean"),
    )
    pooled.to_csv(OUT / "forward_entry_pooled_summary.csv", index=False)
    print("POOLED FORWARD ENTRY SUMMARY")
    print(pooled.round(3).to_string(index=False))
    print("\nSaved results/forward_entry_diagnostics.csv")
    print("Saved results/forward_entry_summary.csv")
    print("Saved results/forward_entry_pooled_summary.csv")
    print("NOTE: overlapping opportunity samples; not independent trades or a portfolio backtest.")


if __name__ == "__main__":
    main()
