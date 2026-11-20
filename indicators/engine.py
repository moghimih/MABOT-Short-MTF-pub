import pandas as pd

from config.settings import (
    EMA_FAST,
    EMA_SLOW,
    EMA_TREND,
    RSI_PERIOD,
    ATR_PERIOD,
    ADX_PERIOD,
)

from indicators.ema import calculate_ema
from indicators.rsi import calculate_rsi
from indicators.atr import calculate_atr
from indicators.adx import calculate_adx


def calculate_segment_indicators(part):
    part = part.copy()

    part["EMA20"] = calculate_ema(
        part["close"], EMA_FAST
    )

    part["EMA50"] = calculate_ema(
        part["close"], EMA_SLOW
    )

    part["EMA200"] = calculate_ema(
        part["close"], EMA_TREND
    )

    part["RSI14"] = calculate_rsi(
        part["close"], RSI_PERIOD
    )

    part["ATR14"] = calculate_atr(
        part, ATR_PERIOD
    )

    adx_data = calculate_adx(
        part, ADX_PERIOD
    )

    part = part.join(adx_data)

    part["indicators_ready"] = (
        part["EMA200"].notna()
        & part["RSI14"].notna()
        & part["ATR14"].notna()
        & part["ADX"].notna()
    )

    return part


def calculate_all_indicators(df):
    if "segment_id" not in df.columns:
        raise ValueError("segment_id column is required")

    results = []

    for segment_id, part in df.groupby(
        "segment_id", sort=False
    ):
        calculated = calculate_segment_indicators(part)

        calculated["segment_id"] = segment_id

        results.append(calculated)

    result = pd.concat(results, ignore_index=True)

    return result