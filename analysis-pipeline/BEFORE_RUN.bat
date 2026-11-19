@echo off
rem Double-click: checks every game folder. Or run with a game name.
cd /d "%~dp0"
where py >nul 2>nul && (py -3 tools\before_run.py %*) || (python tools\before_run.py %*)
echo.
pause
