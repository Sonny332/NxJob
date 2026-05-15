@echo off
setlocal
call "%~dp0scripts\check-health.bat" %*
exit /b %ERRORLEVEL%
