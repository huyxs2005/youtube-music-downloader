@echo off
setlocal
cd /d "%~dp0"
python "%~dp0ytmusic_downloader.py"
echo.
echo Press any key to close this window.
pause >nul
