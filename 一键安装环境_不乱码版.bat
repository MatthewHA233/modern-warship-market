@echo off
chcp 65001 >nul
title Install Environment
color 0A

echo Installing Environment...
echo ========================
echo.

:: Check Python
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    goto :install
)

python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :install
)

color 0C
echo Error: Python not found!
echo Install Python from: https://www.python.org/downloads/
pause
exit

:install
echo Upgrading pip...
%PYTHON_CMD% -m pip install --upgrade pip

echo Installing packages...
%PYTHON_CMD% -m pip install -r AgentScript/requirements.txt

echo Creating folders...
if not exist recording mkdir recording
if not exist cache mkdir cache
if not exist battle_stats mkdir battle_stats

echo.
echo Installation complete!
echo.
pause 