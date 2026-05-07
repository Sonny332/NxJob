@echo off
setlocal
call "%~dp0scripts\start-local-service.bat" %*
exit /b %ERRORLEVEL%
