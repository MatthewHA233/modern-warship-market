@echo off
chcp 65001 >nul
title 现代战舰模板配置工具
color 0B

echo ========================================
echo   现代战舰模板配置工具 v1.0
echo ========================================
echo.

cd /d "%~dp0"

:: 检查是否存在虚拟环境
if exist "AgentScript\venv\Scripts\activate.bat" (
    echo ✅ 检测到虚拟环境，正在激活...
    call AgentScript\venv\Scripts\activate.bat
    if errorlevel 1 (
        echo ❌ 虚拟环境激活失败，尝试使用全局Python...
        goto :use_global_python
    )
    echo ✅ 虚拟环境已激活
    echo.
    echo 正在启动模板配置工具...
    python AgentScript\template_config_tool.py
) else (
    echo 未检测到虚拟环境，使用全局Python...
    :use_global_python
    echo.
    echo 正在启动模板配置工具...
    
    :: 优先尝试py命令
    py AgentScript\template_config_tool.py >nul 2>&1
    if not errorlevel 1 goto :script_ended
    
    :: 备选python命令
    python AgentScript\template_config_tool.py >nul 2>&1
    if not errorlevel 1 goto :script_ended
    
    :: 都失败了
    echo ❌ Python命令执行失败！
    goto :error_handling
)

:script_ended
echo.
echo ✅ 配置工具正常退出
goto :end

:error_handling
echo.
echo ❌ 配置工具运行出错！
echo.
echo 可能的原因：
echo 1. Python环境未正确安装
echo 2. 依赖包未安装（请运行 AgentScript\一键安装环境.bat）
echo 3. PyQt5未安装（pip install PyQt5）
echo 4. OpenCV未安装（pip install opencv-python）
echo 5. 如果使用虚拟环境，请确保环境已正确创建
echo.

:end
echo ================================
echo 程序已退出，按任意键关闭窗口...
pause >nul