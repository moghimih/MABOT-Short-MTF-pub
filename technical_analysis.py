import pandas as pd
import numpy as np
from pathlib import Path

MARKETS = [
    "btcusdt",
    "ethusdt",
    "zecusdt",
    "xrpusdt"
]


def calculate_indicators(df):

    df = df.copy()

    # EMA
    df["EMA20"] = df["close"].ewm(
        span=20, adjust=False
    ).mean()

    df["EMA50"] = df["close"].ewm(
        span=50, adjust=False
    ).mean()

    # RSI
    delta = df["close"].diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1/14,
        adjust=False,
        min_periods=14
    ).mean()

    avg_loss = loss.ewm(
        alpha=1/14,
        adjust=False,
        min_periods=14
    ).mean()

    rs = avg_gain / avg_loss

    df["RSI"] = 100 - (100 / (1 + rs))

    df.loc[
        (avg_loss == 0) & (avg_gain > 0),
        "RSI"
    ] = 100

    df.loc[
        (avg_loss == 0) & (avg_gain == 0),
        "RSI"
    ] = 50

    # MACD
    ema12 = df["close"].ewm(
        span=12, adjust=False
    ).mean()

    ema26 = df["close"].ewm(
        span=26, adjust=False
    ).mean()

    df["MACD"] = ema12 - ema26

    df["MACD_SIGNAL"] = df["MACD"].ewm(
        span=9, adjust=False
    ).mean()

    # ATR
    previous_close = df["close"].shift(1)

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - previous_close).abs(),
        (df["low"] - previous_close).abs()
    ], axis=1).max(axis=1)

    df["ATR"] = tr.ewm(
        alpha=1/14,
        adjust=False,
        min_periods=14
    ).mean()

    # Volume
    df["VOLUME_MA20"] = df["volume"].rolling(
        window=20
    ).mean()

    df["VOLUME_RATIO"] = (
        df["volume"] /
        df["VOLUME_MA20"].replace(0, np.nan)
    )

    return df


def analyze_market(symbol):

    filename = f"{symbol}_history.csv"

    if not Path(filename).exists():
        print(f"File not found: {filename}")
        return

    df = pd.read_csv(filename)
    df = calculate_indicators(df)

    latest = df.iloc[-1]

    required = [
        "EMA20", "EMA50", "RSI",
        "MACD", "MACD_SIGNAL",
        "ATR", "VOLUME_RATIO"
    ]

    if latest[required].isna().any():
        print(f"{symbol}: Insufficient data")
        return

    buy_score = 0
    sell_score = 0

    # 1. EMA trend
    if latest["EMA20"] > latest["EMA50"]:
        buy_score += 1
        trend = "BULLISH"
    elif latest["EMA20"] < latest["EMA50"]:
        sell_score += 1
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    # 2. RSI
    if 50 < latest["RSI"] < 70:
        buy_score += 1
        rsi_status = "BULLISH"

    elif 30 < latest["RSI"] < 50:
        sell_score += 1
        rsi_status = "BEARISH"

    else:
        rsi_status = "NEUTRAL / EXTREME"

    # 3. MACD
    if latest["MACD"] > latest["MACD_SIGNAL"]:
        buy_score += 1
        macd_status = "BULLISH"

    elif latest["MACD"] < latest["MACD_SIGNAL"]:
        sell_score += 1
        macd_status = "BEARISH"

    else:
        macd_status = "NEUTRAL"

    # 4. Price vs EMA20
    if latest["close"] > latest["EMA20"]:
        buy_score += 1
        price_status = "ABOVE EMA20"

    elif latest["close"] < latest["EMA20"]:
        sell_score += 1
        price_status = "BELOW EMA20"

    else:
        price_status = "ON EMA20"

    # Volume confirmation only
    volume_active = latest["VOLUME_RATIO"] >= 1.2

    if volume_active and latest["close"] > latest["open"]:
        volume_status = "BUYERS ACTIVE"

    elif volume_active and latest["close"] < latest["open"]:
        volume_status = "SELLERS ACTIVE"

    else:
        volume_status = "NO CONFIRMATION"

    # Final analytical signal
    if buy_score >= 3 and buy_score > sell_score:
        signal = "BULLISH SETUP"

    elif sell_score >= 3 and sell_score > buy_score:
        signal = "BEARISH SETUP"

    else:
        signal = "WAIT"

    print("\n" + "=" * 48)
    print(f"MARKET: {symbol.upper()}")
    print("=" * 48)

    print(f"Close: {latest['close']:.6f}")
    print(f"EMA20: {latest['EMA20']:.6f}")
    print(f"EMA50: {latest['EMA50']:.6f}")
    print(f"RSI: {latest['RSI']:.2f}")
    print(f"MACD: {latest['MACD']:.6f}")
    print(f"MACD Signal: {latest['MACD_SIGNAL']:.6f}")
    print(f"ATR: {latest['ATR']:.6f}")
    print(f"Volume Ratio: {latest['VOLUME_RATIO']:.2f}")

    print("-" * 48)

    print("Trend:", trend)
    print("RSI Status:", rsi_status)
    print("MACD Status:", macd_status)
    print("Price Status:", price_status)
    print("Volume:", volume_status)

    print("-" * 48)

    print(f"BUY SCORE: {buy_score}/4")
    print(f"SELL SCORE: {sell_score}/4")
    print("MARKET SIGNAL:", signal)

    print("REAL TRADING: DISABLED")

    df.to_csv(
        f"{symbol}_analysis.csv",
        index=False
    )


def main():

    print("=" * 50)
    print("MABOT AI - TECHNICAL ANALYSIS V2")
    print("=" * 50)

    for symbol in MARKETS:

        try:
            analyze_market(symbol)

        except Exception as error:
            print(f"{symbol.upper()} ERROR: {error}")

    print("\nANALYSIS COMPLETED")


if __name__ == "__main__":
    main()