@echo off
setlocal
title Robi RCS
set "SCRIPT_ROOT=%~dp0"
set "APP_ROOT=%SCRIPT_ROOT%"
set "LOGFILE=%TEMP%\RobiRCSRun.log"

if not exist "%APP_ROOT%main.py" (
	if defined ROBI_RCS_HOME if exist "%ROBI_RCS_HOME%\main.py" set "APP_ROOT=%ROBI_RCS_HOME%\"
)

if not exist "%APP_ROOT%main.py" (
	echo [Robi RCS] HIBA: A main.py nem talalhato.
	echo [Robi RCS] Valoszinuleg nincs teljesen kibontva a csomag, vagy meg nincs telepitve az alkalmazas.
	pause
	exit /b 1
)

if not exist "%APP_ROOT%.venv\Scripts\python.exe" (
	echo [Robi RCS] HIBA: A helyi Python kornyezet nem talalhato: "%APP_ROOT%.venv\Scripts\python.exe"
	echo [Robi RCS] Elobb futtasd az Install-RobiRCS.cmd fajlt.
	pause
	exit /b 1
)

pushd "%APP_ROOT%" >nul 2>&1
if errorlevel 1 (
	echo [Robi RCS] HIBA: Nem sikerult megnyitni az alkalmazas mappajat: "%APP_ROOT%"
	pause
	exit /b 1
)

set "OPENEMS_INSTALL_PATH=%APP_ROOT%openEMS"
set "PYTHONUTF8=1"
echo [Robi RCS] Inditas innen: %APP_ROOT% > "%LOGFILE%"
"%APP_ROOT%.venv\Scripts\python.exe" "%APP_ROOT%main.py" >> "%LOGFILE%" 2>&1
set "EXITCODE=%ERRORLEVEL%"
popd

if not "%EXITCODE%"=="0" (
	echo.
	echo [Robi RCS] Az inditas hibaval leallt.
	echo [Robi RCS] Naplo: %LOGFILE%
	echo.
	type "%LOGFILE%"
	pause
)

exit /b %EXITCODE%