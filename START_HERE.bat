@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ==================================================
echo MABOT Paper Trading - Multi Timeframe
echo 1) 1h  - Hourly
echo 2) 4h  - Four hours
echo 3) 1d  - Daily
echo ==================================================
set /p TF_CHOICE=Select timeframe (1/2/3):
if "%TF_CHOICE%"=="1" (
  set TF=1h
  set DB=results\paper_1h.sqlite3
  set LOG=results\logs\paper_1h.log
  set PORT=8081
) else if "%TF_CHOICE%"=="2" (
  set TF=4h
  set DB=results\paper_4h.sqlite3
  set LOG=results\logs\paper_4h.log
  set PORT=8082
) else if "%TF_CHOICE%"=="3" (
  set TF=1d
  set DB=results\paper_1d.sqlite3
  set LOG=results\logs\paper_1d.log
  set PORT=8083
) else (
  echo Invalid choice.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo First run: creating environment...
  py -3.12 -m venv .venv 2>nul || py -3 -m venv .venv 2>nul || python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r requirements-run.txt
if errorlevel 1 (echo Install failed. Check your internet and send me the message above. & pause & exit /b 1)
echo.
echo Starting MABOT on %TF%.
echo This timeframe has its own database and paper account.
echo Keep this window open. Phone address will be printed below.
echo If Windows asks about the firewall, choose Private networks.
".venv\Scripts\python.exe" -m paper_trading.service --share --timeframe %TF% --db %DB% --log-file %LOG% --port %PORT%
pause
