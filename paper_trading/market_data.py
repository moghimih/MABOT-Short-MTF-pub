"""Read-only Nobitex market data client for closed native candles."""
from __future__ import annotations

import time
from dataclasses import dataclass

import pandas as pd
import requests

BASE_URL = "https://apiv2.nobitex.ir/market/udf/history"


TIMEFRAMES = {
    "1m": {"resolution": "1", "seconds": 60},
    "5m": {"resolution": "5", "seconds": 5 * 60},
    "15m": {"resolution": "15", "seconds": 15 * 60},
    "1h": {"resolution": "60", "seconds": 60 * 60},
    "4h": {"resolution": "240", "seconds": 4 * 60 * 60},
    "1d": {"resolution": "D", "seconds": 24 * 60 * 60},
}


@dataclass(frozen=True)
class MarketDataConfig:
    timeframe_seconds: int = 4 * 60 * 60
    countback: int = 300
    timeout_seconds: int = 20
    max_closed_candle_age_seconds: int | None = None


class NobitexPublicDataClient:
    """Fetches public candles only; deliberately has no order/account methods."""

    def __init__(self, session: requests.Session | None = None,
                 config: MarketDataConfig | None = None):
        self.session = session or requests.Session()
        self.config = config or MarketDataConfig()
        self.session.headers.update({"User-Agent": "MABOT-paper-trading/1.0"})

    def fetch_closed(self, symbol: str, timeframe: str = "4h",
                     now_ts: int | None = None) -> pd.DataFrame:
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe {timeframe!r}; choose one of {tuple(TIMEFRAMES)}")
        tf = TIMEFRAMES[timeframe]
        seconds = tf["seconds"]
        now_ts = int(time.time()) if now_ts is None else int(now_ts)
        response = self.session.get(
            BASE_URL,
            params={"symbol": symbol, "resolution": tf["resolution"], "to": now_ts,
                    "countback": self.config.countback},
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("s") != "ok":
            raise RuntimeError(f"Nobitex history error for {symbol}: {payload}")
        fields = ("t", "o", "h", "l", "c", "v")
        if any(key not in payload for key in fields):
            raise ValueError(f"Incomplete OHLCV response for {symbol}")
        lengths = {len(payload[key]) for key in fields}
        if len(lengths) != 1:
            raise ValueError(f"OHLCV array length mismatch for {symbol}: {lengths}")
        frame = pd.DataFrame({
            "timestamp": payload["t"], "open": payload["o"],
            "high": payload["h"], "low": payload["l"],
            "close": payload["c"], "volume": payload["v"],
        })
        if frame.empty:
            raise ValueError(f"No candles returned for {symbol}")
        frame["timestamp"] = pd.to_numeric(frame["timestamp"], errors="raise").astype("int64")
        for col in ("open", "high", "low", "close", "volume"):
            frame[col] = pd.to_numeric(frame[col], errors="raise")
        frame = frame.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
        frame = frame[frame.timestamp + seconds <= now_ts].reset_index(drop=True)
        if frame.empty:
            raise ValueError(f"No fully closed {timeframe} candles for {symbol}")
        latest_close_ts = int(frame.timestamp.iloc[-1]) + seconds
        age = now_ts - latest_close_ts
        max_age = self.config.max_closed_candle_age_seconds
        if max_age is None:
            max_age = 2 * seconds
        if age < 0 or age > max_age:
            raise RuntimeError(f"Stale market data for {symbol}: latest closed candle age={age}s")
        values = frame[["open", "high", "low", "close", "volume"]]
        if not values.notna().all().all() or (values <= 0).any().any():
            raise ValueError(f"Invalid OHLCV values for {symbol}")
        invalid = ((frame.high < frame.low) | (frame.high < frame.open) |
                   (frame.high < frame.close) | (frame.low > frame.open) |
                   (frame.low > frame.close))
        if invalid.any():
            raise ValueError(f"Invalid OHLC relationships for {symbol}")
        return frame


    # Backward-compatible alias for existing tests and scripts.
    def fetch_closed_4h(self, symbol: str, now_ts: int | None = None) -> pd.DataFrame:
        return self.fetch_closed(symbol, "4h", now_ts)
