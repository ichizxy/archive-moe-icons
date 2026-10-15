@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0工具\应用图标.ps1" -WhatIf
set "ARCHIVE_MOE_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %ARCHIVE_MOE_EXIT%
