"""Start independent short-only 1m/5m/15m paper runner and phone dashboard."""
import argparse, json, socket, threading, time
from pathlib import Path
from paper_trading.ops import configure_logging
from paper_trading.short_dashboard import serve
from paper_trading.short_mtf import ShortMTFRunner

def local_ip():
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
            s.connect(('10.255.255.255',1)); return s.getsockname()[0]
    except OSError: return '127.0.0.1'

def main():
    p=argparse.ArgumentParser(description='MABOT short-only MTF paper service')
    p.add_argument('--db',default='results/short_mtf.sqlite3'); p.add_argument('--log-file',default='results/logs/short_mtf.log')
    p.add_argument('--interval',type=int,default=60); p.add_argument('--port',type=int,default=8084); p.add_argument('--share',action='store_true'); p.add_argument('--once',action='store_true')
    a=p.parse_args()
    if a.interval<15:p.error('--interval must be >=15 seconds')
    db=Path(a.db); db.parent.mkdir(parents=True,exist_ok=True); beat=db.parent/(db.stem+'_heartbeat.json')
    log=configure_logging(a.log_file); runner=ShortMTFRunner(db,logger=log)
    print('MABOT SHORT MTF | 1m confirmation + 5m trigger + 15m trend | PAPER ONLY | NO LEVERAGE | NO REAL ORDERS')
    if not a.once:
        host='0.0.0.0' if a.share else '127.0.0.1'; server=serve(db,beat,host,a.port); threading.Thread(target=server.serve_forever,daemon=True).start()
        print(f'Phone dashboard: http://{local_ip()}:{a.port}' if a.share else f'Local dashboard: http://127.0.0.1:{a.port}')
    while True:
        try: results=runner.run_once()
        except Exception as e: log.exception('cycle_error'); results=[{'action':'CYCLE_ERROR','error':str(e)}]
        beat.write_text(json.dumps({'time':int(time.time()),'results':results},ensure_ascii=False),encoding='utf-8')
        print(time.strftime('%H:%M:%S'),' | '.join(f"{r.get('symbol','-')}:{r.get('action')}" for r in results))
        if a.once: break
        time.sleep(a.interval)
if __name__=='__main__': main()
