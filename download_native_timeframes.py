"""MABOT - Download native 4h and 1d candles from Nobitex.

Read-only public market-data requests. No API key and no trading actions.
Saves separate CSV files; does not modify existing historical files.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://apiv2.nobitex.ir/market/udf/history"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "ZECUSDT", "XRPUSDT")
TIMEFRAMES = {
    "4h": {"resolution": "240", "seconds": 4 * 60 * 60},
    "1d": {"resolution": "D", "seconds": 24 * 60 * 60},
}
PAGE_SIZE = 500
MAX_PAGES = 10
REQUEST_TIMEOUT = 25


def fetch_candles(session: requests.Session, symbol: str, resolution: str,
                  candle_seconds: int) -> pd.DataFrame:
    # Freeze the upper time bound so pagination refers to one consistent snapshot.
    fixed_to = int(time.time())
    records: list[dict] = []

    for page in range(1, MAX_PAGES + 1):
        params = {
            "symbol": symbol,
            "resolution": resolution,
            "to": fixed_to,
            "countback": PAGE_SIZE,
            "page": page,
        }
        response = session.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        status = payload.get("s")

        if status == "no_data":
            print(f"  Page {page}: no more data")
            break
        if status != "ok":
            raise RuntimeError(
                f"Nobitex returned status={status!r} for {symbol} {resolution}: "
                f"{payload.get('errmsg', payload)}"
            )

        keys = ("t", "o", "h", "l", "c", "v")
        missing = [key for key in keys if key not in payload]
        if missing:
            raise RuntimeError(f"Response missing fields: {missing}")

        lengths = {len(payload[key]) for key in keys}
        if len(lengths) != 1:
            raise RuntimeError(f"Unequal OHLCV array lengths: {lengths}")

        page_count = len(payload["t"])
        print(f"  Page {page}: {page_count} candles received")

        for timestamp, op, hi, lo, close, volume in zip(
            payload["t"], payload["o"], payload["h"],
            payload["l"], payload["c"], payload["v"]
        ):
            records.append({
                "timestamp": int(timestamp),
                "open": float(op),
                "high": float(hi),
                "low": float(lo),
                "close": float(close),
                "volume": float(volume),
            })

        if page_count < PAGE_SIZE:
            break
        time.sleep(0.35)

    if not records:
        raise RuntimeError(f"No candles returned for {symbol} {resolution}")

    df = pd.DataFrame.from_records(records)
    df = df.sort_values("timestamp")
    df = df.drop_duplicates(subset="timestamp", keep="last").reset_index(drop=True)

    # Keep only fully closed candles. The API timestamp is Unix seconds.
    now_ts = int(time.time())
    df = df[df["timestamp"] + candle_seconds <= now_ts].reset_index(drop=True)

    if df.empty:
        raise RuntimeError(f"No fully closed candles remain for {symbol} {resolution}")

    return df


def report_and_save(symbol: str, timeframe: str, df: pd.DataFrame) -> None:
    seconds = TIMEFRAMES[timeframe]["seconds"]
    timestamps = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    gaps = int((timestamps.diff().dropna() != pd.Timedelta(seconds=seconds)).sum())
    duplicates = int(df["timestamp"].duplicated().sum())
    missing = int(df.isna().sum().sum())
    invalid_ohlc = int((
        (df["high"] < df["low"]) |
        (df["high"] < df["open"]) |
        (df["high"] < df["close"]) |
        (df["low"] > df["open"]) |
        (df["low"] > df["close"])
    ).sum())

    out_name = f"{symbol.lower()}_{timeframe}_native.csv"
    df.to_csv(out_name, index=False)

    print(f"\nRESULT: {symbol} {timeframe}")
    print(f"Candles: {len(df)}")
    print(f"First candle: {timestamps.iloc[0]}")
    print(f"Last candle:  {timestamps.iloc[-1]}")
    print(f"Missing values: {missing}")
    print(f"Duplicate timestamps: {duplicates}")
    print(f"Time gaps: {gaps}")
    print(f"Invalid OHLC: {invalid_ohlc}")
    print(f"Saved: {out_name}")


def main() -> None:
    print("=" * 65)
    print("MABOT - NATIVE NOBITEX TIMEFRAME DATA DOWNLOADER")
    print("PUBLIC READ-ONLY DATA | REAL TRADING: DISABLED")
    print("=" * 65)

    with requests.Session() as session:
        session.headers.update({"User-Agent": "MABOT-research/1.0"})
        for timeframe, config in TIMEFRAMES.items():
            print(f"\n##### NATIVE TIMEFRAME: {timeframe} #####")
            for symbol in SYMBOLS:
                print(f"\nDownloading {symbol}...")
                df = fetch_candles(
                    session,
                    symbol,
                    config["resolution"],
                    config["seconds"],
                )
                report_and_save(symbol, timeframe, df)
                time.sleep(0.35)

    print("\n" + "=" * 65)
    print("DOWNLOAD FINISHED")
    print("Existing historical files were not modified.")
    print("REAL TRADING: DISABLED")
    print("=" * 65)


if __name__ == "__main__":
    main()
