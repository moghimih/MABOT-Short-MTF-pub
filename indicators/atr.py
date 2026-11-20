import pandas as pd


def calculate_atr(df, period=14):
    if period < 1:
        raise ValueError("ATR period must be positive")

    required = {"high", "low", "close"}

    if not required.issubset(df.columns):
        raise ValueError("DataFrame must contain high, low, close")

    previous_close = df["close"].shift(1)

    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - previous_close).abs(),
            (df["low"] - previous_close).abs(),
        ],
        axis=1
    ).max(axis=1)

    atr = tr.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    return atr