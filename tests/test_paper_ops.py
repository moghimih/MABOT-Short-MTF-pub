import logging

import pytest

from paper_trading.ops import configure_logging, retry_call


def test_retry_call_retries_then_returns():
    calls = {"n": 0}
    sleeps = []

    def operation():
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("temporary")
        return "ok"

    result = retry_call(operation, attempts=3, base_delay=0.5, sleep=sleeps.append)
    assert result == "ok"
    assert calls["n"] == 3
    assert sleeps == [0.5, 1.0]


def test_retry_call_raises_after_limit():
    with pytest.raises(TimeoutError):
        retry_call(lambda: (_ for _ in ()).throw(TimeoutError()), attempts=2,
                   base_delay=0, sleep=lambda _: None)


def test_rotating_logger_writes_file(tmp_path):
    logger = configure_logging(tmp_path / "logs" / "paper.log")
    logger.info("phase3-test-marker")
    for handler in logger.handlers:
        handler.flush()
    assert "phase3-test-marker" in (tmp_path / "logs" / "paper.log").read_text()
