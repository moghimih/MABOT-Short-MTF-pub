"""Closed-candle BREAKOUT signal preparation; no exchange order functionality."""
from __future__ import annotations

import pandas as pd

from indicators.engine import calculate_all_indicators
from strategies.breakout import BreakoutStrategy

TIMEFRAME_SECONDS = {"1h": 3600, "4h": 14400, "1d": 86400}


def prepare_breakout_frame(candles: pd.DataFrame, timeframe: str = "4h") -> pd.DataFrame:
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(candles.columns)
    if missing:
        raise ValueError(f"Missing candle fields: {sorted(missing)}")
    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f"Unsupported timeframe {timeframe!r}; choose one of {tuple(TIMEFRAME_SECONDS)}")
    step_seconds = TIMEFRAME_SECONDS[timeframe]
    df = candles.copy().sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    if len(df) < 201:
        raise ValueError("At least 201 closed candles are required for EMA200 warmup")
    gaps = df.timestamp.diff().fillna(step_seconds).ne(step_seconds)
    df["segment_id"] = gaps.cumsum().astype(int) - 1
    df["bars_in_segment"] = df.groupby("segment_id").cumcount() + 1
    df = calculate_all_indicators(df)      # same EMA200/ATR14 as the backtests, restarted per segment
    df.loc[df["bars_in_segment"] < 200, "EMA200"] = float("nan")   # EMA200 is only valid after 200 bars in a segment
    return BreakoutStrategy().generate_signals(df)
