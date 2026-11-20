"""Read-only status page (Persian, mobile friendly) for the paper account. Shows no secrets."""
from __future__ import annotations

import html
import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pandas as pd

TEHRAN = timezone(timedelta(hours=3, minutes=30))


def _fmt_ts(ts) -> str:
    return datetime.fromtimestamp(int(ts), TEHRAN).strftime("%Y-%m-%d %H:%M")


def _table(headers, rows) -> str:
    if not rows:
        return "<p class=m>هنوز چیزی ثبت نشده.</p>"
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f"<div class=t><table><tr>{head}</tr>{body}</table></div>"


def render_html(db_path, heartbeat_path=None, timeframe="4h") -> str:
    db_path = Path(db_path)
    equity = cash = dd = None
    positions, events, snaps, status_rows = [], [], pd.DataFrame(), []
    if db_path.exists():
        with sqlite3.connect(db_path) as con:
            try:
                cash = con.execute("SELECT cash FROM account WHERE id=1").fetchone()[0]
                positions = con.execute("SELECT symbol, quantity, avg_entry, stop_price FROM positions").fetchall()
                events = con.execute(
                    "SELECT event_id, side, symbol, quantity, price FROM events ORDER BY rowid DESC LIMIT 15").fetchall()
                snaps = pd.read_sql_query("SELECT timestamp, equity FROM equity_snapshots ORDER BY timestamp", con)
                status_rows = con.execute(
                    "SELECT symbol, timestamp, close, ema200, entry_channel, bars_in_segment, buy FROM symbol_status ORDER BY symbol").fetchall()
            except sqlite3.Error:
                pass
    if not snaps.empty:
        equity = float(snaps.equity.iloc[-1])
        dd = float((snaps.equity / snaps.equity.cummax() - 1).min() * 100)
    beat = {}
    if heartbeat_path and Path(heartbeat_path).exists():
        try:
            beat = json.loads(Path(heartbeat_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            beat = {}
    age = int(time.time() - beat["time"]) // 60 if beat.get("time") else None
    status = "نامشخص"
    if age is not None:
        status = f"آخرین چرخه {age} دقیقه پیش" + (" ⚠️ ربات احتمالاً متوقف است" if age > 40 else " ✅")
    errors = [r for r in beat.get("results", []) if "ERROR" in str(r.get("action", "")) or "CIRCUIT" in str(r.get("action", ""))]
    cards = [("Equity", f"{equity:.2f}" if equity is not None else "-"),
             ("نقدینگی", f"{cash:.2f}" if cash is not None else "-"),
             ("بیشترین افت", f"{dd:.1f}%" if dd is not None else "-"),
             ("پوزیشن باز", str(len(positions)))]
    cards_html = "".join(f"<div class=c><b>{html.escape(v)}</b><span>{html.escape(k)}</span></div>" for k, v in cards)
    ev_rows = []
    for event_id, side, symbol, qty, price in events:
        parts = str(event_id).split(":")
        when = _fmt_ts(parts[1]) if len(parts) > 1 and parts[1].isdigit() else ""
        kind = parts[2] if len(parts) > 2 else side
        ev_rows.append((when, symbol, kind, f"{qty:.6g}", f"{price:.6g}"))
    market_rows = []
    for symbol, ts, close, ema200, channel, bars, buy in status_rows:
        if ema200 is None or bars < 200:
            state, d200, dch = "در حال گرم شدن (کمتر از ۲۰۰ کندل)", "-", "-"
        else:
            d200 = f"{(close / ema200 - 1) * 100:+.1f}%"
            dch = f"{(close / channel - 1) * 100:+.1f}%" if channel else "-"
            if buy:
                state = "سیگنال خرید"
            elif close <= ema200:
                state = "زیر EMA200: ورود ممنوع"
            else:
                state = "بالای EMA200؛ منتظر شکست سقف ۲۰ کندل"
        market_rows.append((symbol, _fmt_ts(ts), f"{close:.6g}", d200, dch, state))
    pos_rows = [(s, f"{q:.6g}", f"{e:.6g}", f"{sp:.6g}") for s, q, e, sp in positions]
    err_html = ("<h2>خطاها</h2>" + _table(["نماد", "خطا"], [(e.get("symbol", ""), e.get("error", e.get("reason", e.get("action")))) for e in errors])) if errors else ""
    return f"""<!doctype html><html lang=fa dir=rtl><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><meta http-equiv=refresh content=60>
<title>MABOT Paper</title><style>
body{{font-family:system-ui,Tahoma,sans-serif;margin:0;padding:16px;background:#f5f6f8;color:#1b1f24}}
h1{{font-size:20px;margin:0 0 4px}}h2{{font-size:16px;margin:20px 0 8px}}.m{{color:#667}}
.g{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:12px 0}}
.c{{background:#fff;border-radius:10px;padding:12px;box-shadow:0 1px 3px #0001;display:flex;flex-direction:column}}
.c b{{font-size:22px}}.c span{{color:#667;font-size:13px}}.t{{overflow-x:auto}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:10px}}th,td{{padding:8px;text-align:right;border-bottom:1px solid #eee;font-size:13px;white-space:nowrap}}
.w{{background:#fff7e0;border-radius:10px;padding:10px;font-size:13px;margin-top:16px}}
@media(prefers-color-scheme:dark){{body{{background:#14161a;color:#e8eaed}}.c,table{{background:#1e2127}}th,td{{border-color:#2c3038}}.w{{background:#33290f}}}}
</style></head><body>
<h1>MABOT — Paper Trading ({html.escape(str(timeframe))})</h1><div class=m>فقط شبیه‌سازی؛ هیچ سفارش واقعی ارسال نمی‌شود</div>
<div class=m>{html.escape(status)}</div><div class=g>{cards_html}</div>
<h2>چرا معامله‌ای نشده؟ وضعیت بازار</h2>{_table(["نماد","کندل","قیمت","فاصله تا EMA200","فاصله تا سقف ۲۰ کندل","وضعیت"], market_rows)}
<h2>پوزیشن‌های باز</h2>{_table(["نماد","مقدار","ورود","استاپ"], pos_rows)}
<h2>آخرین رویدادها</h2>{_table(["زمان (تهران)","نماد","نوع","مقدار","قیمت"], ev_rows)}{err_html}
<div class=w>تا ۳۰ معامله‌ی بسته و ۸ تا ۱۲ هفته به نتیجه اعتماد نکن.</div></body></html>"""


def make_handler(db_path, heartbeat_path, timeframe="4h"):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?")[0] not in ("/", "/index.html"):
                self.send_error(404)
                return
            body = render_html(db_path, heartbeat_path, timeframe).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):       # keep the console quiet
            pass
    return Handler


def serve(db_path, heartbeat_path, host="127.0.0.1", port=8080, timeframe="4h"):
    server = ThreadingHTTPServer((host, port), make_handler(db_path, heartbeat_path, timeframe))
    return server
