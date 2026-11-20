import numpy as np
import pandas as pd
import pytest
from paper_trading.market_data import TIMEFRAMES, MarketDataConfig, NobitexPublicDataClient
from paper_trading.short_mtf import ShortPaperBroker, _indicators, evaluate_short_signal

class Resp:
    def __init__(self,p): self.p=p
    def raise_for_status(self): pass
    def json(self): return self.p
class Sess:
    def __init__(self,p): self.p=p; self.headers={}; self.calls=[]
    def get(self,*a,**kw): self.calls.append(kw); return Resp(self.p)

def candles(tf, n=260, start=None, step=None, close=None):
    step=step or {"1m":60,"5m":300,"15m":900}[tf]
    if start is None:
        end=1_700_000_100 - (1_700_000_100 % 900)
        start=end-n*step
    vals=np.array(close if close is not None else [100-i*.01 for i in range(n)],dtype=float)
    return pd.DataFrame({"timestamp":[start+i*step for i in range(n)],"open":vals+.05,"high":vals+.2,"low":vals-.2,"close":vals,"volume":np.ones(n)})

def test_market_data_supports_1m_5m_15m():
    assert TIMEFRAMES['1m']['resolution']=='1'
    assert TIMEFRAMES['5m']['resolution']=='5'
    assert TIMEFRAMES['15m']['resolution']=='15'

def test_short_broker_open_cover_and_pnl(tmp_path):
    b=ShortPaperBroker(tmp_path/'s.db',initial_cash=100,fee_rate=.01,slippage_rate=.01)
    assert b.open_short('open1','BTCUSDT',10,2,12,1000)
    p=b.positions()['BTCUSDT']
    assert p['entry']==pytest.approx(9.9)
    assert p['stop']==12
    assert b.cash==pytest.approx(99.802)
    assert b.equity({'BTCUSDT':8})==pytest.approx(103.602)
    assert b.cover('cover1','BTCUSDT',8,1300)
    # cover fills at 8.08; gross = (9.9 - 8.08)*2, less 1% exit fee
    assert b.cash==pytest.approx(103.2804)
    assert b.positions()=={}

def test_short_trailing_stop_only_moves_down(tmp_path):
    b=ShortPaperBroker(tmp_path/'s.db')
    b.open_short('o','ETHUSDT',100,1,110,1)
    b.update_stop('ETHUSDT',105)
    assert b.positions()['ETHUSDT']['stop']==105
    b.update_stop('ETHUSDT',108)
    assert b.positions()['ETHUSDT']['stop']==105

def test_indicators_and_alignment_reject_missing_15m_warmup():
    one=candles('1m'); five=candles('5m'); fifteen=candles('15m',n=100)
    result=evaluate_short_signal(one,five,fifteen)
    assert result['ready'] is False
    assert 'گرم' in result['reason']

def test_market_data_resolution_minute_candles():
    now=2_000_000_000; step=60; latest=now-(now%step)-step
    times=[latest-step,latest]
    payload={'s':'ok','t':times,'o':[100,100],'h':[101,101],'l':[99,99],'c':[100,100],'v':[1,1]}
    sess=Sess(payload); client=NobitexPublicDataClient(sess,MarketDataConfig(max_closed_candle_age_seconds=120))
    frame=client.fetch_closed('BTCUSDT','1m',now)
    assert len(frame)==2
    assert sess.calls[0]['params']['resolution']=='1'

def test_three_timeframe_short_confirmation():
    one=candles('1m',n=260,close=[200-i*.2 for i in range(260)])
    five=candles('5m',n=260,close=[220-i*.25 for i in range(260)])
    fifteen=candles('15m',n=260,close=[300-i*.5 for i in range(260)])
    result=evaluate_short_signal(one,five,fifteen)
    assert result['ready'] is True
    assert result['trend_15m'] is True
    assert result['breakdown_5m'] is True
    assert result['confirm_1m'] is True
    assert result['short_signal'] is True
    assert result['stop'] > result['price']

class FakeClient:
    def __init__(self, frames): self.frames=frames
    def fetch_closed(self, symbol, timeframe): return self.frames[timeframe]

def test_short_mtf_runner_opens_isolated_paper_short(tmp_path):
    from paper_trading.short_mtf import ShortMTFRunner
    frames={
        '1m':candles('1m',n=260,close=[200-i*.2 for i in range(260)]),
        '5m':candles('5m',n=260,close=[220-i*.25 for i in range(260)]),
        '15m':candles('15m',n=260,close=[300-i*.5 for i in range(260)]),
    }
    runner=ShortMTFRunner(tmp_path/'short.db',client=FakeClient(frames))
    result=runner.run_once(['BTCUSDT'])[0]
    assert result['action']=='PAPER_SHORT_OPEN'
    assert 'BTCUSDT' in runner.broker.positions()
    assert runner.broker.positions()['BTCUSDT']['stop'] > runner.broker.positions()['BTCUSDT']['entry']
    assert runner.broker.events()[0][1]=='SHORT_OPEN'
