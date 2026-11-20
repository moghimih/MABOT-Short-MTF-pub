@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==================================================
echo MABOT SHORT MTF - PAPER TRADING ONLY
echo 15m: trend filter  ^|  5m: breakdown  ^|  1m: entry confirmation
echo SHORT ONLY - SYNTHETIC PAPER SIMULATION - NO REAL ORDERS
echo ==================================================
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python environment...
  py -3.12 -m venv .venv 2>nul || py -3 -m venv .venv 2>nul || python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
  echo Could not create Python environment. Install Python 3.10+ and try again.
  pause
  exit /b 1
)
echo Checking required packages...
".venv\Scripts\python.exe" -m pip install -q -r requirements-run.txt
if errorlevel 1 (
  echo Package installation failed. Check internet connection and try again.
  pause
  exit /b 1
)
echo.
echo Starting isolated Short MTF account...
echo Database: results\short_mtf.sqlite3
echo Phone dashboard port: 8084
echo Keep this CMD window open. Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m paper_trading.short_mtf_service --share --interval 60 --db results\short_mtf.sqlite3 --log-file results\logs\short_mtf.log --port 8084
pause
