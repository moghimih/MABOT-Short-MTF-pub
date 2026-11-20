from pathlib import Path

# ==========================================
# MABOT - CENTRAL SETTINGS
# ==========================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"

# ------------------------------------------
# MARKET SETTINGS
# ------------------------------------------

EXCHANGE = "nobitex"

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "ZECUSDT",
    "XRPUSDT",
]

TIMEFRAME = "4h"

# ------------------------------------------
# BACKTEST SETTINGS
# ------------------------------------------

INITIAL_CAPITAL = 100.0

FEE_RATE = 0.002
SLIPPAGE_RATE = 0.0005

WARMUP_BARS = 200

# ------------------------------------------
# INDICATOR SETTINGS
# ------------------------------------------

EMA_FAST = 20
EMA_SLOW = 50
EMA_TREND = 200

RSI_PERIOD = 14
ADX_PERIOD = 14
ATR_PERIOD = 14

# ------------------------------------------
# RISK SETTINGS
# ------------------------------------------

MAX_OPEN_POSITIONS = 2

MAX_RISK_PER_TRADE = 0.01

MAX_PORTFOLIO_RISK = 0.02

# ------------------------------------------
# EXECUTION SAFETY
# ------------------------------------------

LIVE_TRADING_ENABLED = False

PAPER_TRADING_ENABLED = True