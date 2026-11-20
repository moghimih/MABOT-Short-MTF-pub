"""One command: paper runner loop + status page.   python -m paper_trading.service [--share]

--share lets other devices on the same Wi-Fi (your phone) open the status page.
The page is read-only and contains no keys; only use --share on a network you trust.
"""
import argparse
import json
import socket
import threading
import time
from pathlib import Path

from paper_trading.dashboard import serve
from paper_trading.ops import configure_logging
from paper_trading.runner import PaperSignalRunner


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def write_heartbeat(path: Path, results) -> None:
    payload = {"time": int(time.time()),
               "results": [{k: v for k, v in r.items() if k in ("symbol", "action", "error", "reason", "timestamp")}
                           for r in results]}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def main():
    p = argparse.ArgumentParser(description="MABOT paper runner + status page (simulation only)")
    p.add_argument("--db", default="results/mabot_paper.sqlite3")
    p.add_argument("--interval", type=int, default=900)
    p.add_argument("--timeframe", choices=("1h", "4h", "1d"), default="4h")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--share", action="store_true", help="make the status page reachable from your phone (same Wi-Fi)")
    p.add_argument("--once", action="store_true")
    p.add_argument("--log-file", default="results/logs/paper_runner.log")
    args = p.parse_args()
    if args.interval < 60:
        p.error("--interval must be at least 60 seconds")
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    beat = db.parent / f"{db.stem}_heartbeat.json"
    logger = configure_logging(args.log_file)
    runner = PaperSignalRunner(db, logger=logger, timeframe=args.timeframe)
    print(f"MABOT PAPER SERVICE | {args.timeframe} | simulation only | no real orders")
    if not args.once:
        host = "0.0.0.0" if args.share else "127.0.0.1"
        server = serve(db, beat, host, args.port, args.timeframe)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"Status page on this device : http://127.0.0.1:{args.port}")
        if args.share:
            print(f"Status page on your phone  : http://{local_ip()}:{args.port}  (same Wi-Fi)")
    while True:
        try:
            results = runner.run_once()
        except Exception as exc:
            logger.exception("cycle_error")
            results = [{"action": "CYCLE_ERROR", "error": f"{type(exc).__name__}: {exc}"}]
        write_heartbeat(beat, results)
        print(time.strftime("%H:%M:%S"), " | ".join(f"{r.get('symbol', '-')}:{r.get('action')}" for r in results))
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
