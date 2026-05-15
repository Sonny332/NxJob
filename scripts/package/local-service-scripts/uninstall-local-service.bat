@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall-local-service.ps1" %*
set "NXJOB_EXIT=%ERRORLEVEL%"
if not "%NXJOB_NO_PAUSE%"=="1" pause
exit /b %NXJOB_EXIT%
