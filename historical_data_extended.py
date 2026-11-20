import requests
import pandas as pd
import time

BASE_URL = "https://apiv2.nobitex.ir/market/udf/history"

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "ZECUSDT",
    "XRPUSDT"
]

RESOLUTION = "60"
MAX_PAGES = 10
CANDLES_PER_PAGE = 500


def get_history(symbol):

    all_data = []

    print(f"\nDownloading {symbol}...")

    for page in range(1, MAX_PAGES + 1):

        params = {
            "symbol": symbol,
            "resolution": RESOLUTION,
            "to": int(time.time()),
            "countback": CANDLES_PER_PAGE,
            "page": page
        }

        response = requests.get(
            BASE_URL,
            params=params,
            headers={"User-Agent": "MABOT/0.1.0"},
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        if data.get("s") == "no_data":
            print(f"Page {page}: No more data")
            break

        if data.get("s") != "ok":
            raise ValueError(data)

        page_data = pd.DataFrame({
            "timestamp": data["t"],
            "open": data["o"],
            "high": data["h"],
            "low": data["l"],
            "close": data["c"],
            "volume": data["v"]
        })

        if page_data.empty:
            break

        if not (
            page_data["timestamp"].is_monotonic_increasing
        ):
            page_data = page_data.sort_values("timestamp")

        all_data.append(page_data)

        print(
            f"Page {page}: "
            f"{len(page_data)} candles received"
        )

        time.sleep(1)

        if len(page_data) < CANDLES_PER_PAGE:
            break

    if not all_data:
        raise ValueError("No historical data received")

    df = pd.concat(all_data, ignore_index=True)

    df = df.drop_duplicates(
        subset="timestamp"
    )

    df = df.sort_values("timestamp")

    df["datetime"] = pd.to_datetime(
        df["timestamp"],
        unit="s",
        utc=True
    )

    # Remove unfinished candles
    now = int(time.time())

    df = df[
        df["timestamp"] + 3600 <= now
    ].copy()

    if df.empty:
        raise ValueError("No closed candles")

    filename = f"{symbol.lower()}_history_extended.csv"

    df.to_csv(filename, index=False)

    gaps = (
        df["timestamp"].diff().dropna() != 3600
    ).sum()

    print("\nRESULT:", symbol)
    print("Total candles:", len(df))
    print("First candle:", df.iloc[0]["datetime"])
    print("Last candle:", df.iloc[-1]["datetime"])
    print("Time gaps:", gaps)
    print("Saved:", filename)


def main():

    print("=" * 50)
    print("MABOT - EXTENDED HISTORICAL DATA ENGINE")
    print("=" * 50)

    for symbol in SYMBOLS:

        try:
            get_history(symbol)

        except Exception as error:
            print(f"\n{symbol} ERROR: {error}")

        time.sleep(2)

    print("\nEXTENDED DATA COLLECTION FINISHED")


if __name__ == "__main__":
    main()