@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%LocalAppData%\Python\bin\python.exe"
if exist "%PYTHON_EXE%" goto run_downloader

set "PYTHON_EXE="
for /f "delims=" %%I in ('where python.exe 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%I"
if defined PYTHON_EXE goto run_downloader

for /f "delims=" %%I in ('where py.exe 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%I"
if defined PYTHON_EXE goto run_downloader

echo Python could not be found.
echo Install Python, then reopen this launcher.
goto finish

:run_downloader
"%PYTHON_EXE%" "%~dp0ytmusic_downloader.py" %*
if %errorlevel% equ 20 exit /b 0

:finish
echo.
echo Press any key to close this window.
pause >nul
