"""Read-only mobile status page for independent short-only MTF paper account."""
from __future__ import annotations
import html, sqlite3, time
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOCAL=timezone(timedelta(hours=3,minutes=30))
def render(db_path, heartbeat_path=None):
    db=Path(db_path); cash=equity=dd=None; positions=[]; events=[]; status=[]; snaps=[]
    if db.exists():
        with sqlite3.connect(db) as c:
            try:
                cash=c.execute('SELECT cash FROM account WHERE id=1').fetchone()[0]
                positions=c.execute('SELECT symbol,quantity,entry,stop,opened_at FROM positions').fetchall()
                events=c.execute('SELECT side,symbol,quantity,price,pnl,timestamp FROM events ORDER BY rowid DESC LIMIT 20').fetchall()
                status=c.execute('SELECT symbol,timestamp,price,trend15,breakdown5,confirm1,state,reason FROM status ORDER BY symbol').fetchall()
                snaps=c.execute('SELECT timestamp,equity FROM snapshots ORDER BY timestamp').fetchall()
            except sqlite3.Error: pass
    if snaps:
        equity=snaps[-1][1]; peak=-float('inf'); dds=[]
        for _,v in snaps: peak=max(peak,v); dds.append(v/peak-1 if peak else 0)
        dd=min(dds)*100
    def table(headers,rows):
        if not rows:return '<p>هنوز داده‌ای ثبت نشده است.</p>'
        return '<div style="overflow-x:auto"><table><tr>'+''.join(f'<th>{html.escape(x)}</th>' for x in headers)+'</tr>'+''.join('<tr>'+''.join(f'<td>{html.escape(str(x))}</td>' for x in r)+'</tr>' for r in rows)+'</table></div>'
    fmt=lambda ts:datetime.fromtimestamp(int(ts),LOCAL).strftime('%m-%d %H:%M')
    market=[]
    for s,ts,p,t,b,c,state,reason in status:
        market.append((s,fmt(ts),f'{p:.6g}' if p else '-', 'نزولی' if t else 'خنثی/صعودی', 'تأیید' if b else 'ندارد', 'تأیید' if c else 'ندارد',state))
    pos=[(s,f'{q:.6g}',f'{e:.6g}',f'{st:.6g}',fmt(ts)) for s,q,e,st,ts in positions]
    ev=[(side,s,f'{q:.6g}',f'{p:.6g}',f'{pnl:.4f}',fmt(ts)) for side,s,q,p,pnl,ts in events]
    cards=''.join(f'<div class="card"><b>{v}</b><span>{k}</span></div>' for k,v in [('ارزش حساب',f'{equity:.2f}' if equity is not None else '-'),('نقد حساب',f'{cash:.2f}' if cash is not None else '-'),('افت سرمایه',f'{dd:.2f}%' if dd is not None else '-'),('شورت باز',str(len(positions)))])
    return f'''<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="30"><title>MABOT SHORT MTF</title><style>body{{font-family:Tahoma,system-ui;margin:0;padding:16px;background:#f4f6f8;color:#20242a}}h1{{font-size:21px}}h2{{font-size:16px;margin-top:22px}}.muted{{color:#667}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin:14px 0}}.card{{background:white;padding:13px;border-radius:10px;min-width:0}}.card b{{display:block;font-size:22px}}.card span{{font-size:13px;color:#667}}table{{border-collapse:collapse;background:white;width:100%}}td,th{{padding:8px;border-bottom:1px solid #ddd;text-align:right;white-space:nowrap;font-size:12px}}.notice{{padding:12px;background:#fff1d5;border-radius:9px;margin-top:18px;font-size:13px}}@media(prefers-color-scheme:dark){{body{{background:#15171b;color:#eee}}.card,table{{background:#22262d}}td,th{{border-color:#393e47}}.notice{{background:#382d17}}}}</style><h1>MABOT — SHORT MTF (1m / 5m / 15m)</h1><div class="muted">فقط شبیه‌سازی شورت؛ بدون اهرم و بدون سفارش واقعی</div><div class="grid">{cards}</div><h2>وضعیت سه تایم‌فریم</h2>{table(['نماد','آخرین ۵دقیقه','قیمت','روند ۱۵دقیقه','شکست ۵دقیقه','تأیید ۱دقیقه','وضعیت'],market)}<h2>پوزیشن‌های Short باز</h2>{table(['نماد','مقدار','ورود','حدضرر','زمان ورود'],pos)}<h2>آخرین رویدادها</h2>{table(['نوع','نماد','مقدار','قیمت','سود/زیان','زمان'],ev)}<div class="notice">این نسخه آزمایشی است. پیش از ارزیابی، حداقل ۳۰ معامله بسته‌شده و چند هفته داده جمع‌آوری شود. نتایج شبیه‌سازی تضمین‌کننده عملکرد آینده نیست.</div></html>'''

def handler(db,beat):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split('?')[0] not in ('/','/index.html'): self.send_error(404); return
            body=render(db,beat).encode(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self,*args): pass
    return H

def serve(db,beat,host='0.0.0.0',port=8084): return ThreadingHTTPServer((host,port),handler(db,beat))
