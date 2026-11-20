import requests
import pandas as pd
import time

from datetime import datetime, timezone

BASE_URL = "https://apiv2.nobitex.ir/market/udf/history"

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "ZECUSDT",
    "XRPUSDT",
]

RESOLUTION = "60"
COUNT = 200


def get_history(symbol):

    params = {
        "symbol": symbol,
        "resolution": RESOLUTION,
        "to": int(time.time()),
        "countback": COUNT,
    }

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=20,
        headers={"User-Agent": "MABOT/0.1.0"}
    )

    response.raise_for_status()
    data = response.json()

    if data.get("s") != "ok":
        raise ValueError(
            f"API response: {data}"
        )

    df = pd.DataFrame({
        "timestamp": data["t"],
        "open": data["o"],
        "high": data["h"],
        "low": data["l"],
        "close": data["c"],
        "volume": data["v"],
    })

    if df.empty:
        raise ValueError("No candle data")

    if df.isnull().any().any():
        raise ValueError("Missing candle values")

    df["datetime"] = pd.to_datetime(
        df["timestamp"],
        unit="s",
        utc=True
    )

    df = df.sort_values("timestamp")
    df = df.drop_duplicates("timestamp")

    # فقط کندل‌های بسته‌شده
    now = int(time.time())
    df = df[
        df["timestamp"] + 3600 <= now
    ].copy()

    if len(df) < 60:
        raise ValueError(
            f"Not enough closed candles: {len(df)}"
        )

    df.to_csv(
        f"{symbol.lower()}_history.csv",
        index=False
    )

    print(f"\n{symbol}")
    print("Candles:", len(df))
    print("First:", df.iloc[0]["datetime"])
    print("Last:", df.iloc[-1]["datetime"])
    print("Latest Close:", df.iloc[-1]["close"])
    print("Saved:", f"{symbol.lower()}_history.csv")


def main():

    print("=" * 45)
    print("MABOT - HISTORICAL DATA ENGINE")
    print("=" * 45)

    for symbol in SYMBOLS:

        try:
            get_history(symbol)

        except Exception as error:
            print(f"\n{symbol} ERROR: {error}")

        time.sleep(2)

    print("\nHistorical data collection finished.")


if __name__ == "__main__":
    main()