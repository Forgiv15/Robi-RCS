@echo off
setlocal
call "%~dp0installer\Install-RobiRCS.cmd"
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
	echo.
	echo A telepito hibaval allt le. Ne zard be ezt az ablakot, olvasd el a hibat fent.
	pause
)
exit /b %EXITCODE%