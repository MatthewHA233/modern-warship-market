@echo off
chcp 65001 >nul
echo ================================
echo.

cd /d "%~dp0"

echo.

py -3.11 AgentScript\warship_auto_battle.py

echo.
echo ================================
pause >nul 