@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Select report timeframe:
echo 1) 1h
echo 2) 4h
echo 3) 1d
set /p TF_CHOICE=Select (1/2/3):
if "%TF_CHOICE%"=="1" set DB=results\paper_1h.sqlite3
if "%TF_CHOICE%"=="2" set DB=results\paper_4h.sqlite3
if "%TF_CHOICE%"=="3" set DB=results\paper_1d.sqlite3
if not defined DB (echo Invalid choice.& pause & exit /b 1)
".venv\Scripts\python.exe" -m paper_trading.report --db "%DB%"
pause
