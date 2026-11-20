import json
import threading
import time
import urllib.request

from paper_trading.broker import PaperBroker
from paper_trading.dashboard import render_html, serve
from paper_trading.runner import PaperSignalRunner
from paper_trading.service import write_heartbeat


def seeded(tmp_path):
    db = tmp_path / "d.sqlite"
    broker = PaperBroker(db, 100.0, 0.0, 0.0, 2)
    runner = PaperSignalRunner(db, broker=broker, client=object())
    broker.buy("BTCUSDT:1700000000:BUY", "BTCUSDT", 100.0, 0.1, 90.0)
    runner._set_mark("BTCUSDT", 105.0)
    runner._snapshot(1700000000)
    return db


def test_render_shows_account_and_escapes_html(tmp_path):
    db = seeded(tmp_path)
    beat = tmp_path / "heartbeat.json"
    write_heartbeat(beat, [{"symbol": "<b>X</b>", "action": "DATA_OR_PROCESSING_ERROR", "error": "<script>1</script>"}])
    page = render_html(db, beat)
    assert "BTCUSDT" in page and "100" in page and "پوزیشن‌های باز" in page
    assert "<script>1</script>" not in page and "&lt;script&gt;" in page
    assert "viewport" in page                      # mobile friendly


def test_render_works_without_database(tmp_path):
    assert "MABOT" in render_html(tmp_path / "missing.sqlite", tmp_path / "none.json")


def test_status_server_serves_page_read_only(tmp_path):
    db = seeded(tmp_path)
    server = serve(db, tmp_path / "hb.json", "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    try:
        body = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5).read().decode("utf-8")
        assert "BTCUSDT" in body
        req = urllib.request.Request(f"http://127.0.0.1:{port}/", data=b"x", method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
            assert False, "POST must not be accepted"
        except urllib.error.HTTPError as err:
            assert err.code == 501
    finally:
        server.shutdown()


def test_status_table_explains_why_there_is_no_trade(tmp_path):
    import pandas as pd
    from paper_trading.broker import PaperBroker
    db = tmp_path / "s.sqlite"
    runner = PaperSignalRunner(db, broker=PaperBroker(db, 100.0, 0.0, 0.0, 2), client=object())
    n = 260
    frame = pd.DataFrame({"timestamp": [1_700_000_000 + i * 14400 for i in range(n)],
                          "open": [200.0 - 0.2 * i for i in range(n)], "high": [201.0 - 0.2 * i for i in range(n)],
                          "low": [199.0 - 0.2 * i for i in range(n)], "close": [200.0 - 0.2 * i for i in range(n)],
                          "volume": 10.0})
    runner.process_symbol("BTCUSDT", frame)             # steady downtrend: price below EMA200
    page = render_html(db, None)
    assert "زیر EMA200" in page and "BTCUSDT" in page
