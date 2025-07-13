@echo off
chcp 65001 >nul
title 现代战舰代肝脚本 - 环境安装
color 0A

echo ========================================
echo   现代战舰代肝脚本 - 一键安装环境
echo ========================================
echo.

echo [1/4] 检查Python是否已安装...

:: 优先检测py命令（Windows推荐）
py --version >nul 2>&1
if not errorlevel 1 (
    echo ✅ Python已安装 (使用py命令)
    set PYTHON_CMD=py
    goto :python_found
)

:: 检测python命令
python --version >nul 2>&1
if not errorlevel 1 (
    echo ✅ Python已安装 (使用python命令)
    set PYTHON_CMD=python
    goto :python_found
)

:: 未找到Python
color 0C
echo ❌ 错误：未检测到Python！
echo.
echo 解决方案：
echo 1. 访问 https://www.python.org/downloads/
echo 2. 下载并安装Python
echo 3. 安装时务必勾选 "Add Python to PATH"
echo 4. 或者使用Microsoft Store安装Python
echo.
echo 如果已安装Python但仍报错，可能需要重启命令提示符
echo.
pause
exit

:python_found
echo.
echo [2/4] 升级pip...
%PYTHON_CMD% -m pip install --upgrade pip

echo.
echo [3/4] 安装必要的依赖包...
echo.
echo ========================================
echo   选择Python环境类型
echo ========================================
echo.
echo 1. 全局环境 (简单快速，但会占用C盘空间)
echo 2. 虚拟环境 (推荐，隔离依赖，节省空间)
echo.
set /p env_choice=请选择环境类型 (1或2): 

if "%env_choice%"=="1" (
    echo.
    echo 正在安装到全局Python环境...
    echo 注意：这将安装到全局Python环境，会占用大量C盘空间
    %PYTHON_CMD% -m pip install -r AgentScript/requirements.txt
) else if "%env_choice%"=="2" (
    echo.
    echo 正在创建虚拟环境...
    
    :: 检查是否已有虚拟环境
    if exist "venv" (
        echo ✅ 检测到已有虚拟环境，将使用现有环境
    ) else (
        echo 创建新的虚拟环境 'venv'...
        %PYTHON_CMD% -m venv venv
        if errorlevel 1 (
            color 0C
            echo ❌ 虚拟环境创建失败！
            echo 可能需要先安装venv模块: %PYTHON_CMD% -m pip install virtualenv
            pause
            exit
        )
        echo ✅ 虚拟环境创建成功
    )
    
    echo.
    echo 激活虚拟环境并安装依赖...
    call venv\Scripts\activate.bat
    if errorlevel 1 (
        color 0C
        echo ❌ 虚拟环境激活失败！
        pause
        exit
    )
    
    echo 升级虚拟环境中的pip...
    python -m pip install --upgrade pip
    
    echo 安装项目依赖到虚拟环境...
    pip install -r AgentScript/requirements.txt
    
    echo ✅ 虚拟环境配置完成
    echo.
    echo 重要提示：
    echo 每次使用脚本前需要激活虚拟环境：
    echo   cd AgentScript
    echo   venv\Scripts\activate.bat
    echo.
) else (
    echo 无效选择，默认使用全局环境...
    echo 正在安装到全局Python环境...
    echo 注意：这将安装到全局Python环境，会占用大量C盘空间
    %PYTHON_CMD% -m pip install -r AgentScript/requirements.txt
)

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
echo 1. 回到根目录，运行 检查设备连接.bat 检测设备
echo 2. 回到根目录，运行 启动录制脚本.bat 录制战斗
echo 3. 回到根目录，运行 启动代肝脚本.bat 开始代肝
echo.
pause 