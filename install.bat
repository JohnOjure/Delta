@echo off
setlocal

echo [*] Checking for Python...
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [!] Python is not installed or not in PATH.
    echo [!] Please install Python 3.10+ from python.org or the Microsoft Store.
    exit /b 1
)

echo [*] Launching installer...
python install.py

endlocal
