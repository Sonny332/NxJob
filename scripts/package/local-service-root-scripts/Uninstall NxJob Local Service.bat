@echo off
setlocal
call "%~dp0scripts\uninstall-local-service.bat" %*
exit /b %ERRORLEVEL%
