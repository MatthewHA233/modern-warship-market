@echo off
chcp 65001 >nul
title 现代战舰录制脚本
color 0E

echo ========================================
echo   现代战舰战斗录制器
echo ========================================
echo.

cd /d "%~dp0"

echo 正在启动录制脚本...
echo.

python AgentScript\gui_interface.py

if errorlevel 1 (
    echo.
    echo ❌ 录制器启动失败！
    echo.
    echo 请检查：
    echo 1. Python环境是否正确安装
    echo 2. PyQt5是否已安装
    echo 3. 运行 AgentScript\一键安装环境.bat
    echo.
)

echo.
echo ================================
echo 程序已退出，按任意键关闭窗口...
pause >nul 