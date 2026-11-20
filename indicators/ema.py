import pandas as pd


def calculate_ema(series, period):
    if period < 1:
        raise ValueError("EMA period must be positive")

    return series.ewm(
        span=period,
        adjust=False
    ).mean()