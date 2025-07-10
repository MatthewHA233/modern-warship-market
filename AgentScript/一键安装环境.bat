@echo off
chcp 65001 >nul
title 现代战舰代肝脚本 - 环境安装
color 0A

echo ========================================
echo   现代战舰代肝脚本 - 一键安装环境
echo ========================================
echo.

echo [1/4] 检查Python是否已安装...
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo ❌ 错误：未检测到Python！
    echo.
    echo 请先安装Python：
    echo 1. 访问 https://www.python.org/downloads/
    echo 2. 下载并安装Python（记得勾选Add to PATH）
    echo.
    pause
    exit
)
echo ✅ Python已安装

echo.
echo [2/4] 升级pip...
python -m pip install --upgrade pip

echo.
echo [3/4] 安装必要的依赖包...
echo 正在从 requirements.txt 安装依赖...
pip install -r requirements.txt

echo.
echo [4/4] 创建必要的文件夹...
if not exist recording mkdir recording
if not exist cache mkdir cache
if not exist battle_stats mkdir battle_stats
echo ✅ 文件夹创建完成

echo.
echo ========================================
echo   ✅ 环境安装完成！
echo ========================================
echo.
echo 下一步：
echo 1. 回到根目录，运行 启动录制脚本.bat 录制战斗
echo 2. 回到根目录，运行 启动代肝脚本.bat 开始代肝
echo.
pause 