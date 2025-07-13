@echo off
chcp 65001 > nul
echo.

cd /d "%~dp0"
py -3.11 AgentScript/template_config_tool.py

if %errorlevel% neq 0 (
    echo.
    pause
)
