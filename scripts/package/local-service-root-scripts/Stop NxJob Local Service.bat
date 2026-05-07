@echo off
setlocal
call "%~dp0scripts\stop-local-service.bat" %*
exit /b %ERRORLEVEL%
