@echo off
rem Windows: double-click, or drag a run folder onto this file.
cd /d "%~dp0"
set KIT_PAUSE=1
where py >nul 2>nul && (py -3 kit.py recompute %*) || (python kit.py recompute %*)
if errorlevel 9009 (echo Python 3 was not found. Install it from python.org and tick "Add python.exe to PATH". & pause)
