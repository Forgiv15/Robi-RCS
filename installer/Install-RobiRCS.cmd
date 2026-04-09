@echo off
setlocal
set "LOGFILE=%TEMP%\RobiRCSInstaller.log"
echo [Robi RCS] Telepito inditas > "%LOGFILE%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-RobiRCS.ps1" >> "%LOGFILE%" 2>&1
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