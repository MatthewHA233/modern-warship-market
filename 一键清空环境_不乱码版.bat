@echo off
chcp 65001 >nul
title Clean Environment
color 0C

echo Cleaning Environment...
echo ========================
echo.

:: Check Python
py --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    goto :clean
)

python --version >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :clean
)

echo Error: Python not found!
pause
exit

:clean
:: Check AgentScript/requirements.txt
if not exist "AgentScript/requirements.txt" (
    echo Error: AgentScript/requirements.txt not found!
    pause
    exit
)

echo Uninstalling packages from AgentScript/requirements.txt...
%PYTHON_CMD% -m pip uninstall -r AgentScript/requirements.txt -y

echo.
echo Cleaning complete!
echo.
pause 