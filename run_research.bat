@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe -m research.forward_entry_diagnostics
if errorlevel 1 pause
