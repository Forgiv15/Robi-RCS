@echo off
setlocal
set "ROOT=%~dp0"
set "OPENEMS_INSTALL_PATH=%ROOT%openEMS"
set "PYTHONUTF8=1"
"%ROOT%.venv\Scripts\python.exe" "%ROOT%main.py"