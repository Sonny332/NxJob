@echo off
setlocal
call "%~dp0scripts\status-local-service.bat" %*
exit /b %ERRORLEVEL%
