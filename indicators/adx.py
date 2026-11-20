import pandas as pd


def calculate_adx(df, period=14):
    if period < 1:
        raise ValueError("ADX period must be positive")

    required = {"high", "low", "close"}

    if not required.issubset(df.columns):
        raise ValueError("DataFrame must contain high, low, close")

    high = df["high"]
    low = df["low"]
    close = df["close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = up_move.where(
        (up_move > down_move) & (up_move > 0), 0.0
    )

    minus_dm = down_move.where(
        (down_move > up_move) & (down_move > 0), 0.0
    )

    previous_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs()
        ],
        axis=1
    ).max(axis=1)

    atr = tr.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    plus_smoothed = plus_dm.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    minus_smoothed = minus_dm.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    plus_di = 100 * plus_smoothed / atr
    minus_di = 100 * minus_smoothed / atr

    denominator = plus_di + minus_di

    dx = (
        100 * (plus_di - minus_di).abs() / denominator
    ).where(denominator != 0, 0.0)

    adx = dx.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    return pd.DataFrame({
        "ADX": adx,
        "PLUS_DI": plus_di,
        "MINUS_DI": minus_di
    }, index=df.index)