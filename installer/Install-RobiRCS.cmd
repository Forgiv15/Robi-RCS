@echo off
setlocal
set "LOGFILE=%TEMP%\RobiRCSInstaller.log"
title Robi RCS Telepito

echo [Robi RCS] Telepito inditas
echo [Robi RCS] Aktualis mappa: %CD%
echo [Robi RCS] Script mappa: %~dp0

if not exist "%~dp0Install-RobiRCS.ps1" (
	echo [Robi RCS] HIBA: Az Install-RobiRCS.ps1 nem talalhato.
	pause
	exit /b 1
)

echo [Robi RCS] Telepito inditas > "%LOGFILE%"
echo [Robi RCS] Ez nehany percig is eltarthat. Reszletes naplo: %LOGFILE%
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-RobiRCS.ps1" >> "%LOGFILE%" 2>&1
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
	echo.
	echo A telepito hibaval leallt.
	echo Reszletes naplo: %LOGFILE%
	echo.
	type "%LOGFILE%"
	pause
	exit /b %EXITCODE%
)
echo.
echo Telepites kesz.
echo Reszletes naplo: %LOGFILE%
exit /b 0