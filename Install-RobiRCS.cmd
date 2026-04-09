@echo off
setlocal
title Robi RCS Telepito

echo [Robi RCS] Telepito inditasa...
echo [Robi RCS] Forras mappa: %~dp0

if not exist "%~dp0installer\Install-RobiRCS.cmd" (
	echo [Robi RCS] HIBA: Az installer\Install-RobiRCS.cmd nem talalhato.
	echo [Robi RCS] Valoszinuleg nincs teljesen kibontva a csomag.
	pause
	exit /b 1
)

call "%~dp0installer\Install-RobiRCS.cmd"
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
	echo.
	echo A telepito hibaval allt le. Ne zard be ezt az ablakot, olvasd el a hibat fent.
	pause
)
if "%EXITCODE%"=="0" (
	echo.
	echo A telepito befejezodott.
	echo Ha a program kesobb sem indul, nezd meg ezt a naplot: %%TEMP%%\RobiRCSInstaller.log
	pause
)
exit /b %EXITCODE%