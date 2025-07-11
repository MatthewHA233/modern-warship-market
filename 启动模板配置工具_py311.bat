@echo off
chcp 65001 > nul
echo 启动模板配置工具...
echo.

REM 检查ADB是否存在
if not exist "adb.exe" (
    echo 错误：未找到 adb.exe
    echo 请确保 adb.exe 在当前目录中
    pause
    exit /b 1
)

REM 启动模板配置工具
echo 正在启动模板配置工具...
cd /d "%~dp0"
py -3.11 AgentScript/template_config_tool.py

if %errorlevel% neq 0 (
    echo.
    echo 程序执行出错，错误代码：%errorlevel%
    echo 请检查错误信息并重试
    pause
)
