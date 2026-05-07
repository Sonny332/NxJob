@echo off
setlocal
call "%~dp0scripts\install-local-service.bat" %*
exit /b %ERRORLEVEL%
