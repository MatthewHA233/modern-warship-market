@echo off
chcp 65001 >nul
echo 现代战舰录制脚本 - 使用Python 3.11
echo ================================
echo.

cd /d "%~dp0"

echo 正在启动代肝脚本...
echo 使用py -3.11启动器...
echo.

py -3.11 AgentScript\main.py

echo.
echo ================================
echo 程序已退出，按任意键关闭窗口...
pause >nul 