import pandas as pd
import pytest

from paper_trading.market_data import MarketDataConfig, NobitexPublicDataClient
from paper_trading.live_signals import prepare_breakout_frame


class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): pass
    def json(self): return self.payload


class FakeSession:
    def __init__(self, payload): self.payload = payload; self.headers = {}; self.calls = []
    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return FakeResponse(self.payload)


def payload(times):
    n = len(times)
    return {"s": "ok", "t": times, "o": [100]*n, "h": [102]*n,
            "l": [98]*n, "c": [101]*n, "v": [10]*n}


def test_public_client_filters_open_candle_and_deduplicates():
    now = 2_000_000_000
    latest_closed_start = now - (now % 14400) - 14400
    times = [latest_closed_start - 14400, latest_closed_start, latest_closed_start]
    session = FakeSession(payload(times))
    client = NobitexPublicDataClient(session, MarketDataConfig(max_closed_candle_age_seconds=20000))
    frame = client.fetch_closed_4h("BTCUSDT", now)
    assert len(frame) == 2
    assert frame.timestamp.is_monotonic_increasing


def test_public_client_rejects_stale_data():
    now = 2_000_000_000
    old = now - 4 * 14400
    client = NobitexPublicDataClient(FakeSession(payload([old])), MarketDataConfig())
    with pytest.raises(RuntimeError, match="Stale"):
        client.fetch_closed_4h("BTCUSDT", now)


def test_breakout_preparation_resets_warmup_after_gap():
    start = 1_700_000_000
    times = [start + i*14400 for i in range(205)]
    times += [times[-1] + 2*14400 + i*14400 for i in range(205)]
    close = [100 + i*0.01 for i in range(len(times))]
    frame = pd.DataFrame({"timestamp": times, "open": close, "high": [x+1 for x in close],
                          "low": [x-1 for x in close], "close": close, "volume": [1]*len(times)})
    out = prepare_breakout_frame(frame)
    assert out.iloc[204].bars_in_segment == 205
    assert out.iloc[205].bars_in_segment == 1
    assert pd.isna(out.iloc[205].EMA200)
    assert out.iloc[-1].bars_in_segment == 205


@pytest.mark.parametrize(
    ("timeframe", "resolution", "seconds"),
    [("1h", "60", 3600), ("4h", "240", 14400), ("1d", "D", 86400)],
)
def test_native_timeframe_uses_matching_resolution_and_closed_candles(
    timeframe, resolution, seconds
):
    now = 2_000_000_000
    latest_closed_start = now - (now % seconds) - seconds
    session = FakeSession(payload([latest_closed_start - seconds, latest_closed_start]))
    client = NobitexPublicDataClient(session)
    frame = client.fetch_closed("BTCUSDT", timeframe, now)
    assert len(frame) == 2
    assert session.calls[0][1]["params"]["resolution"] == resolution
    assert (frame.timestamp + seconds <= now).all()


def test_breakout_preparation_uses_selected_timeframe_for_gap_detection():
    start = 1_700_000_000
    step = 3600
    times = [start + i * step for i in range(205)]
    times += [times[-1] + 2 * step + i * step for i in range(205)]
    close = [100 + i * 0.01 for i in range(len(times))]
    frame = pd.DataFrame({"timestamp": times, "open": close, "high": [x+1 for x in close],
                          "low": [x-1 for x in close], "close": close, "volume": [1]*len(times)})
    out = prepare_breakout_frame(frame, "1h")
    assert out.iloc[204].bars_in_segment == 205
    assert out.iloc[205].bars_in_segment == 1
