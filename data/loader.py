from pathlib import Path

import pandas as pd

from config.settings import PROJECT_ROOT
from data.validator import print_validation_report


FILE_MAP = {
    "BTCUSDT": "btcusdt_4h_native_gap_aware.csv",
    "ETHUSDT": "ethusdt_4h_native_gap_aware.csv",
    "ZECUSDT": "zecusdt_4h_native_gap_aware.csv",
    "XRPUSDT": "xrpusdt_4h_native_gap_aware.csv",
}


def load_market_data(symbol, validate=True):
    symbol = symbol.upper()

    if symbol not in FILE_MAP:
        raise ValueError(f"Unsupported symbol: {symbol}")

    file_path = PROJECT_ROOT / FILE_MAP[symbol]

    if not file_path.exists():
        raise FileNotFoundError(
            f"Historical data file not found: {file_path}"
        )

    df = pd.read_csv(file_path)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        unit="s",
        utc=True
    )

    if validate:
        valid = print_validation_report(df, symbol)

        if not valid:
            raise ValueError(
                f"Data validation failed for {symbol}"
            )

    return df


def load_all_markets(validate=True):
    markets = {}

    for symbol in FILE_MAP:
        print(f"\nLoading {symbol}...")

        markets[symbol] = load_market_data(
            symbol,
            validate=validate
        )

    return markets