@echo off
chcp 65001 >nul
title 现代战舰代肝脚本
color 0B

echo ========================================
echo   现代战舰代肝脚本 v1.0
echo ========================================
echo.

cd /d "%~dp0"

echo 正在启动代肝脚本...
echo.

python AgentScript\warship_auto_battle.py

if errorlevel 1 (
    echo.
    echo ❌ 脚本运行出错！
    echo.
    echo 可能的原因：
    echo 1. Python环境未正确安装
    echo 2. 依赖包未安装（请运行 AgentScript\一键安装环境.bat）
    echo 3. 手机未连接或USB调试未开启
    echo.
)

echo.
echo ================================
echo 程序已退出，按任意键关闭窗口...
pause >nul 