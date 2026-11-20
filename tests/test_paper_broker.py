import pytest
from paper_trading.broker import PaperBroker
from paper_trading.sizing import quantity_for_risk


def test_buy_sell_fees_slippage_and_cash(tmp_path):
    b = PaperBroker(tmp_path / "paper.db", initial_cash=100, fee_rate=.01,
                    slippage_rate=.01)
    buy = b.buy("c1", "BTCUSDT", 10, 2, 8)
    assert buy.price == pytest.approx(10.1)
    assert buy.fee == pytest.approx(.202)
    assert b.cash == pytest.approx(79.598)
    sell = b.sell("c2", "BTCUSDT", 12)
    assert sell.price == pytest.approx(11.88)
    assert sell.fee == pytest.approx(.2376)
    assert b.cash == pytest.approx(103.1204)
    assert b.positions() == {}


def test_duplicate_event_is_idempotent(tmp_path):
    b = PaperBroker(tmp_path / "paper.db", initial_cash=100)
    first = b.buy("same", "BTCUSDT", 10, 1, 9)
    second = b.buy("same", "BTCUSDT", 10, 1, 9)
    assert first == second
    assert len(b.trades()) == 1


def test_insufficient_cash_and_position_limit(tmp_path):
    b = PaperBroker(tmp_path / "paper.db", initial_cash=10, max_open_positions=1)
    with pytest.raises(ValueError, match="Insufficient"):
        b.buy("a", "BTCUSDT", 10, 2, 9)
    b.buy("b", "BTCUSDT", 5, 1, 4)
    with pytest.raises(ValueError, match="Maximum"):
        b.buy("c", "ETHUSDT", 1, 1, .5)


def test_persistence_after_reopen(tmp_path):
    path = tmp_path / "paper.db"
    b = PaperBroker(path, initial_cash=100)
    b.buy("a", "BTCUSDT", 10, 1, 9)
    restarted = PaperBroker(path, initial_cash=999)
    assert restarted.cash == pytest.approx(b.cash)
    assert "BTCUSDT" in restarted.positions()


def test_validation_and_sizing():
    assert quantity_for_risk(100, 10, 9, .01) == pytest.approx(1)
    with pytest.raises(ValueError):
        quantity_for_risk(100, 10, 10, .01)
    b = PaperBroker(":memory:", initial_cash=100)
    with pytest.raises(ValueError):
        b.buy("x", "BTC", 0, 1, .5)
