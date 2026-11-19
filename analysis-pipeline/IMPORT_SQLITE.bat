@echo off
rem Double-click: works on the newest run folder. Or drag a run folder onto this file.
cd /d "%~dp0"
where py >nul 2>nul && (py -3 tools\import_sqlite.py %*) || (python tools\import_sqlite.py %*)
echo.
pause
